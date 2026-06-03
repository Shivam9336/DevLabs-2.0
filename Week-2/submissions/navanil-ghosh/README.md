# Local AI Agent with Function Calling (Ollama + Llama 3.1)

This repository contains a Python implementation of a local AI agent that uses function calling (tool use) to interact with external APIs. Built using Ollama, Llama 3.1, and Pydantic, the agent handles user queries by dynamically executing local Python functions and feeding the structured results back into the conversational loop.

## 🛠️ System Features

* **Local Inference:** Runs entirely locally using `Ollama` and the `Llama 3.1` model, utilizing its native function-calling capabilities.
* **Type-Safe Schema Validation:** Uses `Pydantic` models to define expected tool parameters, ensuring strict input data validation before execution.
* **Deterministic Output Formatting:** Standardizes API payloads into clean `JSON` strings to prevent parsing errors and hallucinations common in local LLMs.
* **Fault-Tolerant Network Logic:** Implements an automated retry loop with exponential backoff/pauses within the API functions to handle transient connection drops safely.

## 🔌 Integrated Tools & APIs

1. **Local Amenities Locator (`get_local_amenities`):** * Connects to the **OpenStreetMap (Nominatim) API** to search for real-world places (hotels, restaurants, etc.) in a given city.
   * Cleans and truncates long address strings for optimal token efficiency.
2. **Live Time Discovery (`get_timezone_info`):** * Connects to **TimeAPI.io** to pull current time, date, and daylight-saving data for a specific timezone.
   * Contains a 3-pass retry safety mechanism to bypass server timeouts.


