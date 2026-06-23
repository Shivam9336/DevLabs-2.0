# Week 4 Deliverable: Stateful LangGraph Agent

## Graph Structure
This agent utilizes a stateful `StateGraph` architecture to fetch data, draft an itinerary, and integrate human review.

* **`AgentState`:** Tracks the `city`, a reduced `context` list (`operator.add`), the LLM's `answer`, and the number of `attempts`.
* **Nodes:**
    1.  `retrieve`: Asynchronously fetches real-world hotel and restaurant data via OpenStreetMap API to populate the context.
    2.  `generate`: Prompts Llama3 with the backend data and strict guardrails to prevent hallucination. Wrapped in a `try/except` block to gracefully catch failures.
    3.  `send_message`: The final delivery node. Returns an empty dict `{}` to prevent the `operator.add` reducer from duplicating state data.
* **Edges:**
    * `retrieve` -> `generate`
    * **Conditional Edge (`should_continue`):** Implements a ReAct-style retry loop. If `generate` outputs an `"LLM_ERROR:"`, the graph loops back to retry.
    * **Loop Guardrail:** The router tracks `attempts` and forces the loop to exit after 3 tries to prevent infinite execution.
    * `send_message` -> `END`
* **Bonus Implementation:** The graph uses `AsyncSqliteSaver` and is compiled with `interrupt_before=["send_message"]`. Execution pauses, prints the drafted itinerary, accepts terminal input via `input()`, injects the manual human edit directly into the state using `aupdate_state(as_node="generate")`, and finally resumes via `ainvoke(None)`.

---

## Sample Run 1: Successful Single Pass & Human Edit
---

## Sample Run 2: Triggering the Retry Loop
