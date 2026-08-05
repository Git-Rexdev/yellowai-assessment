# Solution Note: Trendly AI Support Agent

## Architecture

The Trendly AI Support Agent is built on **FastAPI** and utilizes **Google's Gemini Flash** via **OpenAI SDK compatibility** (with fallback support for **Groq's Llama 3.3 70B**) to power a **ReAct (Reasoning and Acting) loop**. 

The core interaction loop operates as follows:
1. User messages, contextual system prompts, and tool schemas are sent to the LLM.
2. The LLM evaluates the context.
3. **If the LLM decides to use a tool** (e.g., `lookup_order`, `list_customer_orders`, or `get_policy_info`), it returns a `tool_calls` request.
4. The system executes the corresponding deterministic tool function (out of 9 available tools) and appends the tool output to the conversation history.
5. The loop restarts from step 1, passing the new history back to the LLM.
6. **If the LLM generates a text response**, the loop terminates, and the text is rendered with full Markdown support in the responsive chat UI.

## Key Trade-offs

1. **In-memory sessions vs. Redis/DB**: Opted for in-memory dictionaries for simplicity and ease of setup in this assessment. This sacrifices persistence (restarting the server wipes chat history) for rapid development.
2. **Full policy in system prompt vs. RAG**: Injecting the full markdown policy directly into the prompt ensures minimal latency and maximum context at the cost of higher per-request token usage. For a policy of this size, it's efficient, though it wouldn't scale for massive knowledge bases.
3. **Gemini Flash (via OpenAI SDK) vs. Cloud Models**: Migrated to Google's Gemini Flash via OpenAI SDK compatibility (`GEMINI_API_KEY`). Gemini Flash provides ultra-fast inference, high context efficiency, and robust native tool calling without thought-signature tool loop regressions, while retaining fallback support for Groq (Llama 3.3 70B).
4. **Deterministic tool logic vs. LLM-based decisions**: All business logic (e.g., eligibility rules, return calculations, order listing) runs deterministically in 9 Python tools. The LLM acts purely as an orchestrator and communicator, improving reliability over letting the LLM calculate dates or rules.
5. **Pre-execution guardrails vs. post-processing only**: Implemented defense-in-depth by validating tool arguments before execution (including strict enum constraints on policy topics) and scrubbing input/output, ensuring the model cannot blindly execute harmful or unauthorized actions even if it hallucinates a bad tool call.
6. **Responsive Markdown Chat UI**: Built a custom dark-mode interface supporting full Markdown rendering, touch scrolling, dynamic viewport heights (`100dvh`), and safe-area inset adaptation across mobile and desktop devices.

## Known Limitations

1. **Sessions are in-memory**: Restarting the server clears all conversation history and active sessions.
2. **No real order database**: Returns and exchanges are simulated against mock data in memory.
3. **No authentication**: Customer selection is handled via a UI dropdown for demonstration purposes. In production, this would rely on secure auth tokens.
4. **Policy search is keyword/enum-based**: Enum-based topic filtering (`get_policy_info`) provides reliable section matching, though semantic vector search could be added for arbitrary long-form policy queries.
5. **No support for concurrent requests**: The current state management does not safely handle concurrent requests updating the same session.

## Five Discovery Questions for Trendly's Ops Team

To take this from prototype to production, the following questions need to be addressed by the operations team:

1. What's the current human agent workflow? (ticket system, CRM, etc.) — needed for real escalation integration.
2. What's the peak concurrency profile? (2,000/day average, but what's the burst?) — informs scaling and rate limiting.
3. How are returns currently tracked? (ERP, OMS?) — needed to integrate `initiate_return` with actual systems.
4. What's the acceptable false-positive rate for escalation? — too aggressive = defeats automation, too lenient = bad CX.
5. Are there seasonal/sale-specific policy variations? — the current policy is static; sales events may need dynamic rules.

