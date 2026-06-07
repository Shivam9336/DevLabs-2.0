import json
import os
import sys
from enum import Enum
from typing import Any, Callable
from pydantic import BaseModel, field_validator, model_validator
import requests
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE")
client = Groq(api_key=GROQ_API_KEY, max_retries=0, timeout=12.0)

MODEL_NAME = "openai/gpt-oss-20b"
MARKET_DATA_TIMEOUT = (3, 5)
MARKET_DATA_HEADERS = {"User-Agent": "Mozilla/5.0"}
RAPIDAPI_KEY = "58fb440d6dmsh3b2fe134a76ff0fp1b9b4cjsn8271a590bd3f"
PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


def safe_print(*args: object, sep: str = " ", end: str = "\n") -> None:
    text = sep.join(str(item) for item in args).replace("₹", "Rs.")
    try:
        sys.stdout.write(text + end)
        sys.stdout.flush()
    except UnicodeEncodeError:
        fallback = (text + end).encode(sys.stdout.encoding or "utf-8", errors="replace")
        sys.stdout.buffer.write(fallback)
        sys.stdout.buffer.flush()

class StockInput(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, v: str) -> str:
        v = v.upper().strip()
        if not v:
            raise ValueError("Ticker cannot be empty")
        return v

class PortfolioAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    VALUE = "value"

class PortfolioInput(BaseModel):
    action: PortfolioAction
    ticker: str | None = None
    quantity: float | None = None

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.upper().strip()
    
    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v
    
    @model_validator(mode="after")
    def check_fields(self) -> "PortfolioInput":
        if self.action in {PortfolioAction.ADD, PortfolioAction.REMOVE}:
            if not self.ticker or self.quantity is None:
                raise ValueError(f"Both 'ticker' and 'quantity' are required when performing action '{self.action.value}'")
        return self

def _format_price(value: Any) -> str:
    if value in {None, "", "N/A"}:
        return "N/A"
    try:
        return f"{float(str(value).replace(',', '')):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _get_price_from_rapidapi(ticker: str) -> str | None:
    url = "https://indian-stock-exchange-api2.p.rapidapi.com/stock"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "indian-stock-exchange-api2.p.rapidapi.com",
    }
    querystring = {"name": ticker}

    response = requests.get(
        url,
        headers=headers,
        params=querystring,
        timeout=MARKET_DATA_TIMEOUT,
    )
    if response.status_code != 200:
        return None

    data = response.json()
    price_data = data.get("currentPrice")
    if isinstance(price_data, dict):
        nse_price = _format_price(price_data.get("NSE"))
        bse_price = _format_price(price_data.get("BSE"))
        if nse_price != "N/A" or bse_price != "N/A":
            return f"The current price of {ticker.upper()} is NSE: Rs.{nse_price} and BSE: Rs.{bse_price}."
    elif price_data not in {None, "", "N/A"}:
        return f"The current price of {ticker.upper()} is Rs.{_format_price(price_data)}."

    return None


def _get_price_from_yahoo(ticker: str) -> str | None:
    symbol = _resolve_yahoo_symbol(ticker)
    if not symbol:
        return None
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    response = requests.get(url, headers=MARKET_DATA_HEADERS, timeout=MARKET_DATA_TIMEOUT)
    if response.status_code != 200:
        return None

    data = response.json()
    result = data.get("chart", {}).get("result") or []
    if not result:
        return None

    meta = result[0].get("meta", {})
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    if price is None:
        return None

    label = meta.get("symbol") or symbol
    currency = meta.get("currency") or "INR"
    prefix = "Rs." if currency == "INR" else f"{currency} "
    return f"The current price of {ticker.upper()} ({label}) is {prefix}{_format_price(price)}."


def _resolve_yahoo_symbol(query: str) -> str | None:
    query = query.upper().strip()
    if not query:
        return None
    if query in YAHOO_SYMBOLS:
        return YAHOO_SYMBOLS[query]
    if query.startswith("^") or "." in query:
        return query

    search_url = "https://query2.finance.yahoo.com/v1/finance/search"
    try:
        response = requests.get(
            search_url,
            params={"q": query, "quotesCount": 8, "newsCount": 0},
            headers=MARKET_DATA_HEADERS,
            timeout=MARKET_DATA_TIMEOUT,
        )
        if response.status_code != 200:
            return f"{query}.NS"

        quotes = response.json().get("quotes", [])
        preferred_exchanges = {"NSI", "BSE"}
        preferred_quote_types = {"EQUITY", "INDEX", "ETF"}
        for quote in quotes:
            symbol = quote.get("symbol")
            if (
                symbol
                and quote.get("exchange") in preferred_exchanges
                and quote.get("quoteType") in preferred_quote_types
            ):
                return symbol
        for quote in quotes:
            symbol = quote.get("symbol")
            if symbol and quote.get("quoteType") in preferred_quote_types:
                return symbol
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass

    return f"{query}.NS"


def _get_live_price_value(ticker: str) -> float | None:
    ticker = ticker.upper().strip()

    try:
        url = "https://indian-stock-exchange-api2.p.rapidapi.com/stock"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "indian-stock-exchange-api2.p.rapidapi.com",
        }
        response = requests.get(
            url,
            headers=headers,
            params={"name": ticker},
            timeout=MARKET_DATA_TIMEOUT,
        )
        if response.status_code == 200:
            data = response.json()
            price_data = data.get("currentPrice")
            if isinstance(price_data, dict):
                price = price_data.get("NSE") or price_data.get("BSE")
            else:
                price = price_data
            if price not in {None, "", "N/A"}:
                return float(str(price).replace(",", ""))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass

    try:
        symbol = _resolve_yahoo_symbol(ticker)
        if not symbol:
            return None
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        response = requests.get(
            url,
            headers=MARKET_DATA_HEADERS,
            timeout=MARKET_DATA_TIMEOUT,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        result = data.get("chart", {}).get("result") or []
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        return float(price) if price is not None else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def get_stock_price(ticker: str) -> str:
    ticker = ticker.upper().strip()
    index_queries = {"SENSEX", "BSE SENSEX", "NIFTY", "NIFTY 50", "^BSESN", "^NSEI"}
    providers = (
        (_get_price_from_yahoo, _get_price_from_rapidapi)
        if ticker in index_queries or ticker.startswith("^")
        else (_get_price_from_rapidapi, _get_price_from_yahoo)
    )
    for provider in providers:
        try:
            result = provider(ticker)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            result = None
        if result:
            return result

    return f"Live price data for {ticker} is temporarily unavailable. Please try again in a moment."


def _load_portfolio() -> dict[str, float]:
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as portfolio_file:
            data = json.load(portfolio_file)
        return {
            str(ticker).upper(): float(quantity)
            for ticker, quantity in data.items()
            if float(quantity) > 0
        }
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_portfolio(portfolio: dict[str, float]) -> None:
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as portfolio_file:
        json.dump(portfolio, portfolio_file, indent=2, sort_keys=True)


def manage_portfolio(action: str, ticker: str | None = None, quantity: float | None = None) -> str:
    portfolio = _load_portfolio()

    if action == "add":
        if not ticker or quantity is None:
            return "Ticker and quantity are required to add shares."
        ticker = ticker.upper().strip()
        portfolio[ticker] = portfolio.get(ticker, 0.0) + quantity
        _save_portfolio(portfolio)
        return f"Added {quantity:g} shares of {ticker}. Current holding: {portfolio[ticker]:g} shares."

    if action == "remove":
        if not ticker or quantity is None:
            return "Ticker and quantity are required to remove shares."
        ticker = ticker.upper().strip()
        current_quantity = portfolio.get(ticker, 0.0)
        if current_quantity <= 0:
            return f"{ticker} is not currently in your portfolio."
        if quantity > current_quantity:
            return f"You only have {current_quantity:g} shares of {ticker}; cannot remove {quantity:g}."
        new_quantity = current_quantity - quantity
        if new_quantity > 0:
            portfolio[ticker] = new_quantity
        else:
            portfolio.pop(ticker, None)
        _save_portfolio(portfolio)
        return f"Removed {quantity:g} shares of {ticker}. Remaining holding: {new_quantity:g} shares."

    if action == "value":
        if not portfolio:
            return "Your portfolio is empty."

        total_value = 0.0
        lines = ["Current portfolio valuation:"]
        missing_prices = []
        for held_ticker, held_quantity in sorted(portfolio.items()):
            price = _get_live_price_value(held_ticker)
            if price is None:
                missing_prices.append(held_ticker)
                continue
            position_value = held_quantity * price
            total_value += position_value
            lines.append(
                f"- {held_ticker}: {held_quantity:g} shares x Rs.{price:.2f} = Rs.{position_value:.2f}"
            )

        lines.append(f"Total value: Rs.{total_value:.2f}")
        if missing_prices:
            lines.append(f"Price unavailable for: {', '.join(missing_prices)}")
        return "\n".join(lines)

    return f"Portfolio action '{action}' is not supported."

TOOL_ROUTER: dict[str, Callable[..., Any]] = {
    "get_stock_price": get_stock_price,
    "manage_portfolio": manage_portfolio
}

COMPANY_ALIASES = {
    "adani": "ADANIENT",
    "adani enterprises": "ADANIENT",
    "adani ports": "ADANIPORTS",
    "adani power": "ADANIPOWER",
    "infosys": "INFY",
    "infy": "INFY",
    "sensex": "SENSEX",
    "bse sensex": "SENSEX",
    "nifty": "NIFTY",
    "nifty 50": "NIFTY",
    "reliance": "RELIANCE",
    "tcs": "TCS",
    "tata consultancy": "TCS",
    "hdfc": "HDFCBANK",
    "hdfc bank": "HDFCBANK",
    "icici": "ICICIBANK",
    "icici bank": "ICICIBANK",
    "sbi": "SBIN",
    "state bank of india": "SBIN",
}

YAHOO_SYMBOLS = {
    "ADANIENT": "ADANIENT.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "ADANIPOWER": "ADANIPOWER.NS",
    "SENSEX": "^BSESN",
    "NIFTY": "^NSEI",
    "INFY": "INFY.NS",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
}

nim_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Fetch the current live market price of an Indian stock ticker/company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "The stock symbol or company name, e.g., INFY, RELIANCE"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_portfolio",
            "description": "Perform adjustments to a user's collection of stocks (add, remove) or retrieve overall standing valuation metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "remove", "value"]},
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "quantity": {"type": "number", "description": "Number of shares"}
                },
                "required": ["action"]
            }
        }
    }
]

def _message_from_tool_call(response_message: Any) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": response_message.content or "",
    }

    if response_message.tool_calls:
        message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in response_message.tool_calls
        ]

    return message


def _run_tool(function_name: str, raw_arguments: str | None) -> str:
    try:
        function_args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return "I could not read the tool arguments generated by the model. Please try again with a simpler prompt."

    try:
        if function_name == "get_stock_price":
            validated_data = StockInput(**function_args)
            return str(TOOL_ROUTER[function_name](**validated_data.model_dump()))
        if function_name == "manage_portfolio":
            validated_data = PortfolioInput(**function_args)
            return str(TOOL_ROUTER[function_name](**validated_data.model_dump()))
        return f"The requested tool '{function_name}' is not recognized."
    except Exception as val_err:
        return f"I could not complete the tool request: {val_err}"


def _guess_stock_query(user_prompt: str) -> str | None:
    prompt = user_prompt.lower()
    for alias, ticker in sorted(COMPANY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in prompt:
            return ticker

    words = [
        word.strip(".,?!:;()[]{}\"'")
        for word in user_prompt.split()
        if word.strip(".,?!:;()[]{}\"'")
    ]
    ignored = {
        "what", "is", "the", "current", "market", "price", "of", "right",
        "now", "stock", "share", "tell", "me", "for",
    }
    candidates = [word for word in words if word.lower() not in ignored]
    return candidates[-1].upper() if candidates else None


def run_agent(user_prompt: str) -> str:
    direct_ticker = _guess_stock_query(user_prompt)
    price_words = {"price", "market", "stock", "share", "quote"}
    portfolio_words = {"add", "remove", "portfolio", "holding", "holdings", "valuation", "value"}
    prompt_words = set(user_prompt.lower().split())
    if (
        direct_ticker
        and any(word in user_prompt.lower() for word in price_words)
        and not prompt_words.intersection(portfolio_words)
    ):
        return f"Agent: {get_stock_price(direct_ticker)}"

    messages = [
        {
            "role": "system", 
            "content": "You are a precise financial AI agent. You have access to real-time tools. Use `get_stock_price` for current stock prices and `manage_portfolio` for add, remove, or portfolio valuation requests. NEVER rely on your internal training data for current prices. NEVER say 'As of my knowledge cutoff'. Use plain ASCII text only."
        },
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=nim_tools,
            tool_choice="required",
        )
    except Exception:
        fallback_ticker = _guess_stock_query(user_prompt)
        if fallback_ticker:
            return f"Agent: {get_stock_price(fallback_ticker)}"
        return "Agent: The AI model service is temporarily unavailable. Please try again shortly."

    response_message = response.choices[0].message
    messages.append(_message_from_tool_call(response_message))

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            tool_output = _run_tool(function_name, tool_call.function.arguments)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(tool_output)
            })
        
        try:
            final_response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
            )
            answer = final_response.choices[0].message.content
            if answer:
                return f"Agent: {answer}"
            return f"Agent: {tool_output}"
        except Exception:
            return f"Agent: {tool_output}"

    return f"Agent: {response_message.content or 'I could not generate a response for that request.'}"

if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        if not sys.stdin.isatty():
            safe_print("Agent: This runner cannot accept typed input.")
            safe_print("Agent: Run this file in the Terminal, or pass a prompt like:")
            safe_print('Agent: python "Stockprice_&_portfolio_agent.py" "what is the price of infosys"')
            sys.exit(0)
        try:
            prompt = input("User: ").strip()
        except EOFError:
            safe_print("Agent: No input was received. Please run this from the Terminal.")
            sys.exit(0)

    if prompt:
        if sys.argv[1:]:
            safe_print(f"User: {prompt}")
        safe_print(run_agent(prompt))
    else:
        safe_print("Agent: Please enter a question.")
