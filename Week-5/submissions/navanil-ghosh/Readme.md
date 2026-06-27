# Week 5: Multi-Agent Customer Service Bot

This is a multi-agent system built with LangGraph, Python `asyncio`, and Llama 3 (via Ollama). It acts as a customer service bot that can answer questions about product inventory and store policies at the same time. 

## Agent Topology

The system uses a main orchestrator graph that coordinates two separate worker graphs. State is kept isolated—the orchestrator only passes specific sub-queries to each worker and pulls back the final text.

* **Orchestrator (Main Graph)**
  * Reads the user's query and splits it into two distinct tasks (inventory and policy). 
  * Runs both workers in parallel. If a topic isn't mentioned in the prompt, it dynamically skips calling that worker to save time.
  * A Synthesizer node waits for both workers to finish and merges their answers into one response.

* **Inventory Worker (Separate Sub-Graph)**
  * Extracts search parameters (name, color) into JSON.
  * Uses Pandas to check `inventory.csv` and returns strict stock counts.

* **Policy Worker (Separate Sub-Graph)**
  * Reads `policy.txt` to answer rules-based questions.
  * Includes a self-correction loop: a Verifier node checks the generated answer against the text file. If the LLM hallucinates a rule, it forces it to retry.

## Fault Tolerance & Parallel Execution
The orchestrator triggers the workers concurrently using `asyncio.gather(..., return_exceptions=True)`. If a worker crashes (e.g., if a file is missing or Pandas fails), it doesn't kill the main loop. The exception is caught, the orchestrator logs the error for that specific worker, and the Synthesizer still outputs whatever good data it got from the other worker.

---

## Sample Runs

### 1. Perfect Execution
```
Type 'exit' or 'quit' to close the terminal.

do u have s24 in black, and what is the return policy
[Supervisor] Decomposing query...
Inventory Task: s24 in black
Policy Task: what is the return policy
[Inventory Worker] Extracting search parameters...
[Policy Worker] retrieving policy document...
[Policy Worker] Analyzing policy text...
[Inventory Worker] Querying CSV with Pandas...
[Policy Worker] Verifying responce...
[supervisor] merging the two responses
I'd be happy to help you with your query!

According to our current inventory data, we do have the S24 in black and it is currently in stock. We have 15 units available.

Regarding our return policy, I can confirm that according to our company policy, all returns must be made within 14 days of purchase. Additionally, open box items may incur a 15% restocking fee. Please note that any items damaged by the user are not eligible for return.

So, if you're interested in purchasing the S24 in black and have any questions about the return process or need further clarification on our policy, feel free to ask!
quit

Shutting down agents... Goodbye!
```
### inventory.csv not available and the policy worker returns bad responce
```
Type 'exit' or 'quit' to close the terminal.

I need a white iPhone, and how many days do I have to return it?
[Supervisor] Decomposing query...
Inventory Task: white iPhone
Policy Task: how many days do I have to return it
[Inventory Worker] Extracting search parameters...
[Policy Worker] retrieving policy document...
[Policy Worker] Analyzing policy text...
[Policy Worker] Verifying responce...
[Inventory Worker] Querying CSV with Pandas...
[Policy Worker] Analyzing policy text...    #loops
[Policy Worker] Verifying responce...
[Policy Worker] Analyzing policy text...    #loops again
[Policy Worker] Verifying responce...
[supervisor] merging the two responses
I apologize, but our inventory database is currently offline, and we don't have any information on available products, including white iPhones.

Regarding your return question, according to our Policy Document, you have 14 days from the date of purchase to return an item. Since there's no specific guidance for open box items or damaged items, it's best to follow this general guideline.

Please note that we can't provide information on product availability at this time due to the database being offline. If you're interested in purchasing a white iPhone when our inventory becomes available, I recommend checking with us again.
quit

Shutting down agents... Goodbye!
```
