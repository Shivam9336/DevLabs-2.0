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
```
Running graph...
Fetching data for Tokyo...

Prompting LLM with retrieved context...


 HUMAN REVIEW NEEDED:
Hello!

I'm excited to help you plan your trip to Tokyo! Based on the backend data provided, here's a suggested itinerary for you:

**Hotels:**

1. Hotel Empire in Shinjuku
2. Bat's Man (in Henn na Hotel)
3. マロウド･イン東京

Please note that hotel contact information (phone number and website) is not available.

**Restaurants:**

1. Tokyo In April - Phone: +1-604-423-2779, Website: https://www.tokyoinapril.com/
2. Tokyo in Modena - Phone: +39 059 2928109, Website: https://www.tokyoingalleria.com/

Please note that the third restaurant, Tokyo in galleria, does not have available contact information.

I hope this helps you plan your trip to Tokyo! If you need any further assistance or recommendations, feel free to ask.


Type your edits here (or press ENTER to approve): Goodluck for your trip, Sayonara!(bye in japanese)

[Injecting edit into state...]

Resuming graph...
Delivering final verdict to client:
Hello!

I'm excited to help you plan your trip to Tokyo! Based on the backend data provided, here's a suggested itinerary for you:

**Hotels:**

1. Hotel Empire in Shinjuku
2. Bat's Man (in Henn na Hotel)
3. マロウド･イン東京

Please note that hotel contact information (phone number and website) is not available.

**Restaurants:**

1. Tokyo In April - Phone: +1-604-423-2779, Website: https://www.tokyoinapril.com/
2. Tokyo in Modena - Phone: +39 059 2928109, Website: https://www.tokyoingalleria.com/

Please note that the third restaurant, Tokyo in galleria, does not have available contact information.

I hope this helps you plan your trip to Tokyo! If you need any further assistance or recommendations, feel free to ask.

HUMAN AMENDMENT: Goodluck for your trip, Sayonara!(bye in japanese)
```
---

## Sample Run 2: Triggering the Retry Loop
```
Running graph...
Fetching data for Tokyo...

Prompting LLM with retrieved context...

! LLM failed on attempt 1. Looping back to try again...

Prompting LLM with retrieved context...

! LLM failed on attempt 2. Looping back to try again...

Prompting LLM with retrieved context...


 HUMAN REVIEW NEEDED:
LLM_ERROR: (model 'L-llm' not found (status code: 404))


Type your edits here (or press ENTER to approve): purposefully using wrong llm name to stimulate failure.

[Injecting edit into state...]

Resuming graph...
Delivering final verdict to client:
LLM_ERROR: (model 'L-llm' not found (status code: 404))

HUMAN AMENDMENT: purposefully using wrong llm name to stimulate failure.
```
