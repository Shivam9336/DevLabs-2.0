import operator
import asyncio
import requests
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from ollama import AsyncClient

class AgentState(TypedDict):
    book_query: str
    context: Annotated[list[str], operator.add]
    answer: str
    attempts: int

def fetch_books(book_query: str) -> list[str]:
    """
    Fetch books from Open Library API
    """
    url="https://openlibrary.org/search.json"
    params={
        "q": book_query,
        "limit": 5
    }
    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )
        data = response.json()
        books = data.get("docs", [])

        if not books:
            return ["SYS_MSG: No books found"]
        results = []

        for book in books:
            title=book.get("title", "Unknown")
            authors =", ".join(book.get("author_name", ["Unknown"]))
            year =book.get( "first_publish_year","N/A")
            isbn ="N/A"
            if book.get("isbn"):
                isbn = book["isbn"][0]
            dense_string = (
                f"TITLE:{title} | "
                f"AUTHOR:{authors} | "
                f"YEAR:{year} | "
                f"ISBN:{isbn}"
            )
            results.append(dense_string)
        return results

    except Exception as e:
        return [f"SYS_ERR: Book API failed: {str(e)}"]

async def retrieve_node(state: AgentState) -> dict:
    query=state.get("book_query", "")
    print(f"\nFetching books for '{query}'...\n")
    books = await asyncio.to_thread(
        fetch_books,
        query
    )
    context=["BOOK_DATA\n"] + books
    return {"context": context}

async def generate_node(state: AgentState) -> dict:
    attempts=state.get("attempts", 0) + 1
    query=state.get("book_query", "")
    context=state.get("context", [])
    print("Prompting LLM with retrieved books...\n")
    context_str = "\n".join(context)
    system_prompt = (
        "You are an expert bookstore assistant. "
        "Use ONLY the books provided in BACKEND DATA. "
        "Do not invent books. "
        "If no books are available, clearly say so. "
        "Provide a neat recommendation and summary."
    )

    try:
        response=await AsyncClient().chat(
            model="llama3",
            messages=[
                {
                    "role": "system",
                    "content":system_prompt
                },
                {
                    "role":"user",
                    "content":
                    f"""
User wants books related to: {query}
BACKEND DATA:
{context_str}
"""
                }
            ]
        )

        answer=response["message"]["content"]

    except Exception as e:
        answer = f"LLM_ERROR: {str(e)}"
    return {
        "answer": answer,
        "attempts": attempts
    }

def should_continue(state: AgentState) -> str:
    answer = state.get("answer", "")
    attempts = state.get("attempts", 0)
    if (answer.startswith("LLM_ERROR:")and attempts < 3):
        print(f"LLM failed on attempt {attempts}. Retrying...\n")
        return "retry"
    return "done"

async def send_message_node(state: AgentState) -> dict:
    print("\nFinal Recommendation:\n")
    print(state["answer"])
    return {}

workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate",generate_node)
workflow.add_node("send_message",send_message_node)
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve","generate")
workflow.add_conditional_edges(
    "generate",
    should_continue,
    {
        "retry": "generate",
        "done": "send_message"
    }
)
workflow.add_edge("send_message",END)

async def main():
    async with AsyncSqliteSaver.from_conn_string(
        "bookstore_checkpoints.db"
    ) as checkpointer:
        app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["send_message"]
        )
        config = {
            "configurable": {
                "thread_id": "bookstore_agent_001"
            }
        }
        query = input("Enter book topic/title/author: ")
        print("\nRunning graph...\n")
        await app.ainvoke(
            {
                "book_query": query,
                "attempts": 0,
                "context": []
            },
            config=config
        )
        current_state = await app.aget_state(config)
        draft = current_state.values.get("answer","")
        print("\n========== HUMAN REVIEW ==========\n")
        print(draft)
        human_edit = input("\nEnter edits (Press ENTER to approve): ")
        if human_edit.strip():
            updated_answer = (draft+ "\n\nHUMAN EDIT:\n"+ human_edit)
            await app.aupdate_state(
                config,
                {"answer": updated_answer},
                as_node="generate"
            )
        print("\nResuming graph...\n")
        await app.ainvoke(None,config=config)
if __name__ == "__main__":
    asyncio.run(main())
