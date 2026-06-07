# 📈 Stock Price & Portfolio Management AI Agent

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Groq](https://img.shields.io/badge/Groq-API-orange?style=for-the-badge)
![Pydantic](https://img.shields.io/badge/Pydantic-Validation-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

A highly responsive, AI-powered command-line interface (CLI) agent for real-time stock market tracking and portfolio management. Built using the **Groq API** for lightning-fast LLM tool-calling, this agent seamlessly parses natural language queries to fetch live Indian stock exchange data and manage a local, persistent financial portfolio.

Ideal for algorithmic trading enthusiasts, quantitative finance researchers, or anyone who wants a streamlined terminal interface for market analysis without the bloat of traditional web dashboards.

---

## ✨ Key Features

* **🧠 Intelligent Intent Parsing:** Leverages the `openai/gpt-oss-20b` model via Groq to interpret complex user queries and execute the correct underlying functions.
* **📊 Real-Time Market Data:** Fetches live pricing for NSE/BSE stocks and indices using dual-provider redundancy:
    * *Primary:* Indian Stock Exchange API (via RapidAPI).
    * *Fallback:* Yahoo Finance API.
* **💼 Persistent Portfolio Management:** Add, remove, and evaluate your holdings using simple conversational commands. Data is safely stored locally in `portfolio.json`.
* **🛡️ Robust Input Validation:** Utilizes Pydantic to ensure all tickers and quantities extracted by the LLM are sanitized and logically sound before execution.
* **⚡ Fallback Mechanisms:** Built-in regex and string-matching fallbacks ensure stock prices are retrieved even if the LLM service experiences downtime.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed and configured:

* **Python:** 3.10 or higher.
* **API Keys:**
    * [Groq API Key](https://console.groq.com/) (for the LLM engine).
    * [RapidAPI Key](https://rapidapi.com/) (subscribed to the *Indian Stock Exchange API 2*).

---

## 🚀 Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/yourusername/stock-portfolio-agent.git](https://github.com/yourusername/stock-portfolio-agent.git)
    cd stock-portfolio-agent
    ```

2.  **Install Dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    pip install requests pydantic groq
    ```

3.  **Configure API Keys:**
    Open `Stockprice_&_portfolio_agent.py` and replace the placeholder API keys at the top of the file with your own credentials:
    ```python
    GROQ_API_KEY = "your_groq_api_key_here"
    RAPIDAPI_KEY = "your_rapidapi_key_here"
    ```

---

## 💻 Usage

You can interact with the agent directly through your terminal. Pass your query as an argument or run the script interactively.

### **Method 1: Direct Command-Line Arguments**
```bash
python Stockprice_&_portfolio_agent.py "What is the current price of Reliance?"