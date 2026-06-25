# BookStore Agent using LangGraph

## Graph Structure

This project implements a stateful BookStore Agent using LangGraph. The agent retrieves book information from the Open Library API, generates recommendations using Llama 3, and supports Human-in-the-Loop review before delivering the final response.

### AgentState

Tracks:

* `book_query` → User's search query
* `context` → Retrieved book data (uses `operator.add` reducer)
* `answer` → Generated recommendation
* `attempts` → Retry counter

### Nodes

**retrieve**

* Fetches real-time book data from the Open Library API.
* Stores retrieved book information in the shared state.

**generate**

* Sends retrieved book data to Llama 3 using Ollama.
* Generates book recommendations using only the backend data.
* Handles model failures using try/except.

**send_message**

* Displays the final approved recommendation.

### Edges

```text
retrieve -> generate
```

### Conditional Edge (should_continue)

Implements a ReAct-style retry loop.

If the LLM returns an `LLM_ERROR`, the graph retries generation.

### Loop Guardrail

The graph tracks `attempts` and exits after 3 tries to prevent infinite execution.

```text
generate -> retry -> generate
```

### Final Edge

```text
send_message -> END
```

### Bonus Features

* AsyncSqliteSaver Checkpointing
* thread_id based execution
* Human-in-the-Loop using `interrupt_before=["send_message"]`
* State editing with `aupdate_state()`
* Resume execution using `ainvoke(None, config)`

---

# Sample Run 1: Successful Single Pass

```text
Enter book topic/title/author: machine learning

Running graph...

Fetching books for 'machine learning'...

Prompting LLM with retrieved books...

========== HUMAN REVIEW ==========

What a great selection of machine learning books!

Based on our BACKEND DATA, I highly recommend "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow" by Aurélien Géron. This book is perfect for anyone looking to get hands-on experience with popular machine learning libraries like scikit-learn, Keras, and TensorFlow.

Another excellent choice would be "Machine Learning" by Ethem Alpaydin (2016).

If you're looking for a more introductory text, "Introduction to Machine Learning" by Ethem Alpaydin (2004) would be a great starting point.

And finally, if you're interested in exploring the broader implications of machine learning, "Why Machines Learn" by Anil Ananthaswamy (2024) is an intriguing choice.

These books are all available in our collection, so feel free to check them out!

Enter edits (Press ENTER to approve):

Resuming graph...

Final Recommendation:

What a great selection of machine learning books!

Based on our BACKEND DATA, I highly recommend "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow" by Aurélien Géron.

Another excellent choice would be "Machine Learning" by Ethem Alpaydin (2016).

If you're looking for a more introductory text, "Introduction to Machine Learning" by Ethem Alpaydin (2004) would be a great starting point.

And finally, if you're interested in exploring the broader implications of machine learning, "Why Machines Learn" by Anil Ananthaswamy (2024) is an intriguing choice.

These books are all available in our collection, so feel free to check them out!
```

---

# Sample Run 2: Triggering the Retry Loop

```text
Enter book topic/title/author: machine learning

Running graph...

Fetching books for 'machine learning'...

Prompting LLM with retrieved books...

LLM failed on attempt 1. Retrying...

Prompting LLM with retrieved books...

LLM failed on attempt 2. Retrying...

Prompting LLM with retrieved books...

========== HUMAN REVIEW ==========

LLM_ERROR: model 'wrong-model' not found (status code: 404)

Enter edits (Press ENTER to approve):

Resuming graph...

Final Recommendation:

LLM_ERROR: model 'wrong-model' not found (status code: 404)
```

