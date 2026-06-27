import operator
import asyncio
import json
from ollama import AsyncClient
import pandas as pd
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class InventoryState(TypedDict):
    query: str
    context: Annotated[list[str], operator.add]
    answer: str
    attempts: int

async def inventory_query_node(state: InventoryState) -> dict:
    print("[Inventory Worker] Extracting search parameters...")
    
    system_prompt = (
        "You are a strict data extraction assistant for an inventory system. "
        "Extract search parameters based on two searchable columns: 'name' and 'color'. "
        "Return ONLY a valid JSON dictionary."
    )

    response = await AsyncClient().chat(
        model="llama3",
        format="json", 
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["query"]}
        ]
    )
    
    json_str = response["message"]["content"].strip()

    return {"answer": json_str}

async def inventory_retrieve_node(state: InventoryState) -> dict:
    print("[Inventory Worker] Querying CSV with Pandas...")
    
    json_str = state["answer"] 
    
    try:
        search_params = json.loads(json_str)
    except json.JSONDecodeError:
        return {"answer": "Database Error: LLM final_ansiled to format search parameters."}

    try:
        df = pd.read_csv("inventory.csv")
        filtered_df = df

        for key, value in search_params.items():
            if key in df.columns:
                filtered_df = filtered_df[filtered_df[key].str.contains(str(value), case=False, na=False)]

        if filtered_df.empty:
            result_text = "Item not found in inventory."
        else:
            results = []
            for index, row in filtered_df.iterrows():
                results.append(f"- {row['name']} ({row['color']}): {row['stock']} in stock")
            result_text = "\n".join(results)
            
        return {"answer": result_text}

    except FileNotFoundError:
        return {"answer": "Database offline: inventory.csv is missing."}
    except Exception as e:
        return {"answer": f"Database error: {str(e)}"}

inventory_graph = StateGraph(InventoryState)
inventory_graph.add_node("query", inventory_query_node)
inventory_graph.add_node("retrieve", inventory_retrieve_node)
inventory_graph.set_entry_point("query")

inventory_graph.add_edge("query", "retrieve")
inventory_graph.add_edge("retrieve", END)

inventory_worker = inventory_graph.compile()

class PolicyState(TypedDict):
    query: str
    context: str
    answer: str
    attempts: int
    is_valid: bool

async def policy_retrieve_node(state: PolicyState) -> dict:
    print(f"[Policy Worker] retrieving policy document...")
    try:
        with open("policy.txt", "r") as f:
            return {"context": f.read()}
    except FileNotFoundError:
        return {"context": "Policy document not found."}
    except Exception as e:
        return {"context": f"Error: {str(e)}"}

async def policy_generate_node(state: PolicyState) -> dict:
    print("[Policy Worker] Analyzing policy text...")
    
    context = state["context"]
    
    system_prompt = (
        "You are a strict legal compliance assistant. "
        "Answer the user's query using ONLY the provided Policy Document. "
        "You may use basic logic to match synonyms (e.g., 'opening a box' means 'open box item'). "
        "If the answer is truly not in the document, reply EXACTLY with: 'The company policy does not specify.' "
        "Keep your answer under three sentences."
    )

    user_content = (
        f"User Query: {state['query']}\n\n"
        f"Policy Document:\n{context}"
    )
    
    response = await AsyncClient().chat(
        model="llama3", 
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    
    return {"answer": response["message"]["content"], 'attempts': state.get('attempts',0) + 1}

async def policy_verifier_node(state: PolicyState) -> dict:
    print(f"[Policy Worker] Verifying responce...")
    
    system_prompt = (
        "You are a strict legal verification assistant. "
        "Verify if the LLM's answer violates or contradicts the Policy Document. "
        "Return ONLY a valid JSON dictionary with a single boolean key 'is_valid'. "
        "Set it to true if the answer is safe and accurate, or False if it hallucinates."
    )
    
    user_content = (
        f"LLM Answer: {state['answer']}\n\n"
        f"Policy Document:\n{state['context']}"
    )
    
    response = await AsyncClient().chat(
        model="llama3",
        options={'temperature':0.0},
        format="json",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    
    try:
        decision_data = json.loads(response["message"]["content"])
        is_valid = decision_data.get("is_valid", False) 
    except json.JSONDecodeError:
        print("[Policy Worker] LLM final_ansiled to output JSON. Definal_ansulting to retry.")
        is_valid = False
    
    return {"is_valid": is_valid}

async def policy_varification_state(state: PolicyState) -> str:
    if state.get("is_valid"):
        return 'done'
    if state.get('attempts', 0) >= 3:
        return 'done'
    return 'retry'

policy_graph = StateGraph(PolicyState)
policy_graph.add_node("retrieve", policy_retrieve_node)
policy_graph.add_node("generate", policy_generate_node)
policy_graph.add_node("verify", policy_verifier_node)
policy_graph.set_entry_point("retrieve")

policy_graph.add_edge("retrieve", "generate")
policy_graph.add_edge("generate", "verify")
policy_graph.add_conditional_edges(
    "verify",
    policy_varification_state,
    {'retry': 'generate', 'done': END}
)

policy_worker = policy_graph.compile()

class SupervisorState(TypedDict):
    query: str 
    inventory_result: str
    policy_result: str
    final_response: str

async def orchestrator_node(state: SupervisorState) -> dict:
    print("[Supervisor] Decomposing query...")
    
    split_prompt = (
        "You are a routing assistant. Read the user's query and split it into two distinct questions. "
        "Extract ONLY the part relevant to inventory/stock, and ONLY the part relevant to rules/returns. "
        "Return your answer strictly as a JSON dictionary with keys 'inv_query' and 'pol_query'. "
        "If a topic is not mentioned, leave the string empty."
        'both queries are going to seperate agents so make sure both agents have all the required information to perform their task'
    )
    
    response = await AsyncClient().chat(
        model="llama3", 
        options={'temperature':0.0},
        format="json",
        messages=[
            {"role": "system", "content": split_prompt},
            {"role": "user", "content": state["query"]}
        ]
    )
    
    try:
        queries = json.loads(response["message"]["content"])
        inv_query = queries.get("inv_query", "")
        pol_query = queries.get("pol_query", "")
    except json.JSONDecodeError:
        inv_query = state["query"]
        pol_query = state["query"]

    print(f"Inventory Task: {inv_query}")
    print(f"Policy Task: {pol_query}")

    inv_input = {"query": inv_query, "context": [], "answer": "", "attempts": 0}
    pol_input = {"query": pol_query, "context": '', "answer": "", "attempts": 0, "is_valid": False}
    
    inv_res = "No inventory information was requested."
    pol_res = "No policy information was requested."
    
    task={}
    if inv_query:
        inv_input = {"query": inv_query, "context": [], "answer": "", "attempts": 0}
        task['inventory'] = inventory_worker.ainvoke(inv_input)
  
    if pol_query:
        pol_input = {"query": pol_query, "context": "", "answer": "", "attempts": 0, "is_valid": False}
        task['policy'] = policy_worker.ainvoke(pol_input)
        
    if task:
        results = await asyncio.gather(*task.values(), return_exceptions=True)
        processed = dict(zip(task.keys(), results))
        
        if "inventory" in processed:
            res = processed["inventory"]
            if isinstance(res, Exception):
                inv_res = f"Error: {res}"
            else:
                inv_res = res.get("answer", "Unreachable.")
            
        if "policy" in processed:
            res = processed["policy"]
            if isinstance(res, Exception):
                pol_res = f"Error: {res}"
            else:
                pol_res = res.get("answer", "Unreachable.")

    return {"inventory_result": inv_res, "policy_result": pol_res}

async def synthesize_node(state: SupervisorState) -> dict:    
    system_prompt = (
        "You are a helpful customer service agent. "
        "Answer the user's query using STRICTLY the provided Inventory Data and Policy Data. "
        "CRITICAL: Do NOT invent outside concepts like warranties, trade-ins, store credit, or managers. "
        "If a solution isn't in the provided data, politely inform the user that those are the only rules we have."
    )
    
    user_content = (
        f"User Query: {state['query']}\n\n"
        f"Inventory Data: {state['inventory_result']}\n"
        f"Policy Data: {state['policy_result']}"
    )
    
    print('[supervisor] merging the two responses')
    
    response = await AsyncClient().chat(
        model="llama3", 
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    
    final_ans=response["message"]["content"]
    return {"final_response": final_ans}

main_graph = StateGraph(SupervisorState)
main_graph.add_node("orchestrator", orchestrator_node)
main_graph.add_node("synthesize", synthesize_node)
main_graph.set_entry_point("orchestrator")

main_graph.add_edge("orchestrator", "synthesize")
main_graph.add_edge("synthesize", END)

app = main_graph.compile()

if __name__ == "__main__":
    async def chat_loop():
        print("Type 'exit' or 'quit' to close the terminal.\n")
        while True:
            user_input = input()
            
            if user_input.strip().lower() in ['exit', 'quit']:
                print("\nShutting down agents... Goodbye!")
                break
            if not user_input.strip():
                continue
            final_state = await app.ainvoke({"query": user_input})
            print(final_state["final_response"])

    asyncio.run(chat_loop())
