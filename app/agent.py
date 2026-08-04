import json
import logging
from groq import Groq

from app.prompts import build_system_message, build_customer_context_message
from app.tools import TOOL_SCHEMAS, execute_tool
from app.guardrails import validate_tool_call, check_agent_response, scrub_sensitive_data_from_input
from app.data import get_customer

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10


class ConversationSession:
    def __init__(self, session_id: str, customer_id: str):
        self.session_id = session_id
        self.customer_id = customer_id
        self.customer = get_customer(customer_id)
        self.messages: list[dict] = []
        self.escalated = False
        self.turn_count = 0

        self.messages.append(build_system_message())
        if self.customer:
            self.messages.append(build_customer_context_message(customer_id, self.customer["name"]))

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self.turn_count += 1

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_call_id: str, content: str):
        self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})


class TrendlyAgent:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.sessions: dict[str, ConversationSession] = {}

    def get_or_create_session(self, session_id: str, customer_id: str) -> ConversationSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationSession(session_id, customer_id)
        return self.sessions[session_id]

    def chat(self, session_id: str, customer_id: str, user_message: str) -> dict:
        session = self.get_or_create_session(session_id, customer_id)

        if session.escalated:
            return {
                "response": "This conversation has been transferred to a human agent. They'll be with you shortly. Our support hours are 9:00 AM - 9:00 PM IST, seven days a week.",
                "escalated": True,
                "tool_calls": [],
            }

        scrubbed_message, data_found = scrub_sensitive_data_from_input(user_message)
        if data_found:
            session.add_user_message(scrubbed_message)
            return {
                "response": "I noticed you may have shared sensitive financial information. For your security, I've removed it from this conversation. Please never share bank details, card numbers, or CVV in chat. If we need those for a refund, a human agent will reach out through a secure link.",
                "escalated": False,
                "tool_calls": [],
            }

        session.add_user_message(user_message)

        tool_calls_log = []
        iterations = 0

        while iterations < MAX_ITERATIONS:
            iterations += 1
            logger.info(f"[{session_id}] Iteration {iterations}")

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=session.messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=1024,
                )
            except Exception as e:
                err_str = str(e)
                logger.error(f"Groq API error: {err_str}")
                if "tool_use_failed" in err_str or "Failed to call a function" in err_str:
                    # Retry turn without tools if tool formatting failed
                    try:
                        fallback_resp = self.client.chat.completions.create(
                            model=self.model,
                            messages=session.messages,
                            temperature=0.3,
                            max_tokens=1024,
                        )
                        response_text = fallback_resp.choices[0].message.content or ""
                        session.add_assistant_message(response_text)
                        return {"response": response_text, "escalated": session.escalated, "tool_calls": tool_calls_log}
                    except Exception as inner_e:
                        logger.error(f"Fallback completion error: {inner_e}")
                return {
                    "response": "I'm sorry, I'm experiencing a technical issue right now. Please try again in a moment, or I can connect you with a human agent.",
                    "escalated": False,
                    "tool_calls": tool_calls_log,
                }

            choice = response.choices[0]
            message = choice.message

            if message.tool_calls:
                session.messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in message.tool_calls
                    ],
                })

                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}
                        logger.error(f"Invalid JSON in tool args: {tool_call.function.arguments}")

                    logger.info(f"[{session_id}] Tool call: {fn_name}({fn_args})")

                    violation = validate_tool_call(fn_name, fn_args, session.customer_id)
                    if violation:
                        logger.warning(f"Guardrail violation: {violation.message}")
                        result = json.dumps({"error": violation.message, "blocked_by": "guardrail"})
                    else:
                        if "customer_id" in fn_args:
                            fn_args["customer_id"] = session.customer_id
                        result = execute_tool(fn_name, fn_args)

                    if fn_name == "escalate_to_human":
                        try:
                            esc_result = json.loads(result)
                            if esc_result.get("escalated"):
                                session.escalated = True
                        except json.JSONDecodeError:
                            pass

                    tool_calls_log.append({"name": fn_name, "arguments": fn_args, "result_preview": result[:200]})
                    session.add_tool_result(tool_call.id, result)

                continue

            response_text = message.content or ""

            violation = check_agent_response(response_text)
            if violation:
                logger.warning(f"Response guardrail violation: {violation.message}")
                session.messages.append({
                    "role": "system",
                    "content": f"[GUARDRAIL] Your previous response was blocked: {violation.message}. Please rephrase without offering unauthorized discounts, collecting sensitive data, or inventing policy. Stick to what the policy document says.",
                })
                if iterations < MAX_ITERATIONS:
                    continue
                response_text = "I apologize, but I'm unable to help with that specific request. Let me connect you with a human agent who can assist you further."
                session.escalated = True

            session.add_assistant_message(response_text)
            return {"response": response_text, "escalated": session.escalated, "tool_calls": tool_calls_log}

        logger.error(f"[{session_id}] Max iterations ({MAX_ITERATIONS}) reached")
        fallback = "I apologize, but I'm having trouble processing your request right now. Let me connect you with a human agent who can help."
        session.add_assistant_message(fallback)
        return {"response": fallback, "escalated": False, "tool_calls": tool_calls_log}

    def reset_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
