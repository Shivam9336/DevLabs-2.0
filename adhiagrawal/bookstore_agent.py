"""
Book Store AI Agent with Memory
Uses Hugging Face Inference API

Install:
    pip install huggingface_hub

Run:
    python bookstore_agent.py
"""

from huggingface_hub import InferenceClient
# =====================================================
# TOOLS
# =====================================================

def search_books(query):
    books={
        "python":[
            "Python Crash Course",
            "Automate the Boring Stuff",
            "Fluent Python"
        ],
        "ai":[
            "Hands-On Machine Learning",
            "Deep Learning with Python",
            "AI Engineering"
        ],
        "fiction":[
            "Harry Potter",
            "The Hobbit",
            "Percy Jackson"
        ]
    }

    query=query.lower()

    for category,items in books.items():
        if category in query:
            return f"Found books: {', '.join(items)}"
    return "No books found."


def get_book_price(book_name):
    prices = {
        "Python Crash Course":799,
        "Automate the Boring Stuff":650,
        "Fluent Python":1200,
        "Hands-On Machine Learning":1500,
        "Deep Learning with Python":1100,
        "AI Engineering":999,
        "Harry Potter":500,
        "The Hobbit":450,
        "Percy Jackson":400
    }

    if book_name not in prices:
        return "Book not found."
    return f"{book_name} costs ₹{prices[book_name]}"


def check_availability(book_name):
    stock={
        "Python Crash Course": 13,
        "Automate the Boring Stuff": 0,
        "Fluent Python": 4,
        "Hands-On Machine Learning": 2,
        "Deep Learning with Python": 6,
        "AI Engineering": 12,
        "Harry Potter": 15,
        "The Hobbit": 8,
        "Percy Jackson": 20
    }
    if book_name not in stock:
        return "Book not found."
    qty = stock[book_name]
    if qty == 0:
        return "OUT OF STOCK"
    return f"{qty} copies available"


# =====================================================
# AGENT
# =====================================================

class BookStoreAgent:
    def __init__(self):
        self.client = InferenceClient(
            api_key="your api key"
        )
        self.memory=[]
        self.system_prompt = """
You are a smart bookstore assistant.

Rules:
- Use conversation history.
- Recommend books.
- Answer briefly.
- Remember previous user interests.
"""

# -------------------------------------------------
# MEMORY
# -------------------------------------------------

    def add_memory(self, user, assistant):
        self.memory.append({
            "user": user,
            "assistant": assistant
        })

        # last 5 chats
        self.memory = self.memory[-5:]

    def get_history(self):
        history = ""
        for chat in self.memory:
            history += (
                f"User: {chat['user']}\n"
                f"Assistant: {chat['assistant']}\n\n"
            )
        return history

# -------------------------------------------------
# TOOL ROUTER
# -------------------------------------------------

    def use_tool(self, query):
        q=query.lower()
        if "python" in q:
            return search_books("python")
        elif "ai" in q:
            return search_books("ai")
        elif "fiction" in q:
            return search_books("fiction")
        elif "harry potter" in q and "price" in q:
            return get_book_price("Harry Potter")
        elif "hobbit" in q and "price" in q:
            return get_book_price("The Hobbit")
        elif "python crash course" in q and "price" in q:
            return get_book_price("Python Crash Course")
        elif "available" in q or "stock" in q:
            if "harry potter" in q:
                return check_availability("Harry Potter")
            if "ai engineering" in q:
                return check_availability("AI Engineering")
            if "python crash course" in q:
                return check_availability("Python Crash Course")
        return "No tool result."

# -------------------------------------------------
# LLM
# -------------------------------------------------

    def call_llm(self, user_query, tool_result):
        history = self.get_history()
        prompt = f"""
Conversation History:
{history}
Current User Query:
{user_query}
Tool Result:
{tool_result}

Generate final helpful bookstore response.
"""
        response = self.client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct",
            messages=[
                {
                    "role":"system",
                    "content":self.system_prompt
                },
                {
                    "role":"user",
                    "content":prompt
                }
            ],
            max_tokens=300
        )
        return response.choices[0].message.content

# -------------------------------------------------
# MAIN
# -------------------------------------------------

    def run(self, user_query):
        tool_result = self.use_tool(user_query)
        answer = self.call_llm(
            user_query,
            tool_result
        )
        print("\nAgent:", answer)
        self.add_memory(
            user_query,
            answer
        )


# =====================================================
# CHAT LOOP
# =====================================================

if __name__ == "__main__":
    agent = BookStoreAgent()
    queries=[
        "Suggest me some python books",
        "Which one is cheapest?",
        "Do you have AI books?",
        "What is the price of Harry Potter?",
        "history"
    ]

    for user_input in queries:
        print(f"\nYou: {user_input}")
        if user_input.lower() == "history":
            print("\n=== CHAT HISTORY ===")
            if not agent.memory:
                print("No history found.")
            else:
                for chat in agent.memory:
                    print(f"\nUser: {chat['user']}")
                    print(f"Agent: {chat['assistant']}")
            print("\n=====================")
            continue
        agent.run(user_input)
        
