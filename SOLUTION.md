# Solution Note: Trendly AI Support Agent

## Architecture

The Trendly AI Support Agent is built on **FastAPI** and utilizes **Groq's function calling** capabilities (via Llama 3.3 70B) to power a **ReAct (Reasoning and Acting) loop**. 

The core interaction loop operates as follows:
1. User messages, contextual system prompts, and tool schemas are sent to the LLM.
2. The LLM evaluates the context.
3. **If the LLM decides to use a tool** (e.g., to fetch an order or verify policy), it returns a `tool_calls` request.
4. The system executes the corresponding deterministic tool functions and appends the tool output to the conversation history.
5. The loop restarts from step 1, passing the new history back to the LLM.
6. **If the LLM generates a text response**, the loop terminates, and the text is returned to the user via the API.

## Key Trade-offs

1. **In-memory sessions vs. Redis/DB**: Opted for in-memory dictionaries for simplicity and ease of setup in this assessment. This sacrifices persistence (restarting the server wipes chat history) for rapid development.
2. **Full policy in system prompt vs. RAG**: Injecting the full markdown policy directly into the prompt ensures minimal latency and maximum context at the cost of higher per-request token usage. For a policy of this size, it's efficient, though it wouldn't scale for massive knowledge bases.
3. **Groq (Llama 3.3 70B) vs. OpenAI GPT-4o**: Used Groq with Llama 3.3 70B for free, high-speed inference. The model is sufficiently capable for function calling in this constrained domain, and Groq's speed (tokens/sec) makes the agent feel snappier than cloud-hosted alternatives.
4. **Deterministic tool logic vs. LLM-based decisions**: All business logic (e.g., eligibility rules, return calculations) runs deterministically in Python tools. The LLM acts purely as an orchestrator and communicator, improving reliability over letting the LLM calculate dates or rules.
5. **Pre-execution guardrails vs. post-processing only**: Implemented defense-in-depth by validating tool arguments before execution and scrubbing input/output, ensuring the model cannot blindly execute harmful or unauthorized actions even if it hallucinates a bad tool call.

## Known Limitations

1. **Sessions are in-memory**: Restarting the server clears all conversation history and active sessions.
2. **No real order database**: Returns and exchanges are simulated against mock data in memory.
3. **No authentication**: Customer selection is handled via a UI dropdown for demonstration purposes. In production, this would rely on secure auth tokens.
4. **Policy search is keyword-based**: Simple text matching might miss edge cases compared to semantic vector search.
5. **No support for concurrent requests**: The current state management does not safely handle concurrent requests updating the same session.

## Five Discovery Questions for Trendly's Ops Team

To take this from prototype to production, the following questions need to be addressed by the operations team:

1. What's the current human agent workflow? (ticket system, CRM, etc.) — needed for real escalation integration.
2. What's the peak concurrency profile? (2,000/day average, but what's the burst?) — informs scaling and rate limiting.
3. How are returns currently tracked? (ERP, OMS?) — needed to integrate `initiate_return` with actual systems.
4. What's the acceptable false-positive rate for escalation? — too aggressive = defeats automation, too lenient = bad CX.
5. Are there seasonal/sale-specific policy variations? — the current policy is static; sales events may need dynamic rules.
