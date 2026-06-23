import operator
import asyncio
import requests
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from ollama import AsyncClient

class AgentState(TypedDict):
    city: str
    context: Annotated[list[str], operator.add]
    answer: str
    attempts: int

def fetch_amenity(city: str, amenity: str) -> list[str]:
    """Fetches and compresses API data for optimal LLM consumption."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{amenity} in {city}", 
        "format": "json", 
        "limit": 3,
        "extratags": 1 
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if not data:
            return [f"SYS_MSG: No {amenity}s found."]
            
        results = []
        for place in data:
            name = place.get('name', 'Unknown')
            address = place.get('display_name', 'N/A').split(',')[0] 
            tags = place.get('extratags', {})
            dense_string = f"[{amenity.upper()}] NAME:{name} | ADDR:{address} | PH:{tags.get('phone', 'N/A')} | WEB:{tags.get('website', 'N/A')}"
            results.append(dense_string)

        return results
        
    except Exception as e:
        return [f"SYS_ERR: {amenity} API failed: {str(e)}"]

async def retrieve_node(state: AgentState) -> dict:
    city = state.get("city", "Kolkata")
    
    print(f"Fetching data for {city}...\n")
    
    hotels, restaurants = await asyncio.gather(
        asyncio.to_thread(fetch_amenity, city, "hotel"),
        asyncio.to_thread(fetch_amenity, city, "restaurant")
    )

    context = (["HOTEL_DATA\n"] + hotels + ["\nRESTAURANT_DATA\n"] + restaurants)

    return {"context": context}

async def generate_node(state: AgentState) -> dict:
    attempts = state.get("attempts", 0) + 1
    context = state.get("context", [])
    city = state.get("city", "")

    print("Prompting LLM with retrieved context...\n")

    context_str = "\n".join(context)
    system_prompt = (
        f"You are an expert, professional travel agent drafting a trip to {city}. "
        "Look at the 'BACKEND DATA' provided below. You are ONLY allowed to use the hotels and restaurants listed there."
        "Do not add any other attractions, landmarks, or places from your own memory."
        "If it is not written in the data, it does not exist. "
        "Format the output cleanly and always start with a friendly greeting."
    )

    try:
        response = await AsyncClient().chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"BACKEND DATA:\n{context_str}"}
            ]
        )
        answer = response["message"]["content"]
        
    except Exception as e:
        answer = f"LLM_ERROR: ({str(e)})"
        
    return {"answer": answer, "attempts": attempts}

def should_continue(state: AgentState) -> str:
    answer = state.get("answer", "")
    attempts = state.get("attempts", 0)
    if answer.startswith("LLM_ERROR:") and attempts < 3:
        print(f"! LLM failed on attempt {attempts}. Looping back to try again...\n")
        return "retry"
    return "done"

async def send_message_node(state: AgentState) -> dict:
    print(f"Delivering final verdict to client:\n{state['answer']}")
    return {}

workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("send_message", send_message_node)
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_conditional_edges(
    "generate", 
    should_continue, 
    {"retry": "generate", "done": "send_message"}
)
workflow.add_edge("send_message", END)

async def main():
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        app = workflow.compile(
            checkpointer=checkpointer, 
            interrupt_before=["send_message"]
        )
        config = {"configurable": {"thread_id": "travel_agent_001"}} 
        print("Running graph...")
        await app.ainvoke({"city": "Tokyo", "attempts": 0, "context": []}, config=config)

        current_state = await app.aget_state(config)
        draft = current_state.values.get("answer", "")

        print("\n HUMAN REVIEW NEEDED:")
        print(draft)
        print("\n")

        human_edit = input("Type your edits here (or press ENTER to approve): ")
        
        if human_edit.strip():
            print("\n[Injecting edit into state...]")
            new_answer = draft + f"\n\n*** HUMAN AMENDMENT: {human_edit} ***"
            
            await app.aupdate_state(
                config,
                {"answer": new_answer},
                as_node="generate" 
            )

        print("\nResuming graph...")
        await app.ainvoke(None, config=config)

if __name__ == "__main__":
    asyncio.run(main())
