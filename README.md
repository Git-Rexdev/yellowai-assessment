# Trendly AI Support Agent

AI-powered customer support agent for Trendly, an Indian D2C fashion retailer. Handles order inquiries, returns, exchanges, and policy questions using Gemini API / Groq LLM with function calling.

## Quick Start

1. Clone the repo:
   ```bash
   git clone https://github.com/Git-Rexdev/yellowai-assessment.git
   cd yellowai-assessment
   ```
2. Create and activate virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Add your `GEMINI_API_KEY` (or `GROQ_API_KEY`) to `.env` (get a Gemini API key free at Google AI Studio or Groq key at [console.groq.com](https://console.groq.com)).

5. Start the server:
   ```bash
   python server.py
   ```
6. Open [http://localhost:8000](http://localhost:8000)

## Project Structure

```
app/                  # Core application package
  agent.py            # ReAct orchestration loop (Gemini / Groq function calling via OpenAI SDK)
  data.py             # Order/customer data access layer
  guardrails.py       # Input/output safety validation
  prompts.py          # System prompt with embedded policy
  tools.py            # 9 deterministic tools + function schemas (includes list_customer_orders)
static/               # Responsive dark-mode chat UI with markdown rendering
  index.html
  style.css
  app.js
tests/                # Test suite
  test_tools.py       # Unit tests for all tools (13 tests)
  test_guardrails.py  # Guardrail enforcement tests (7 tests)
  test_agent_e2e.py   # End-to-end conversation tests
server.py             # FastAPI entry point
orders.json           # Fixed order dataset
trendly_policy.md     # Shipping and returns policy
```

## API Endpoints

- `GET /` -- Serves the responsive frontend chat UI
- `GET /api/health` -- Health check
- `GET /api/customers` -- Returns customer list for the UI selector
- `POST /api/chat` -- Processes user messages and returns agent response

## Testing

```bash
# Unit tests (no API key needed)
pytest tests/test_tools.py tests/test_guardrails.py -v

# E2E tests (requires GEMINI_API_KEY or GROQ_API_KEY)
pytest tests/test_agent_e2e.py -v
```

## AI Usage Note

This project uses Gemini Flash (via OpenAI SDK compatibility) or Groq's Llama 3.3 70B model for natural language understanding and function calling. The model is guided by a system prompt that grounds responses in the Trendly policy document. All 9 tool implementations use deterministic logic -- the LLM orchestrates, the tools decide.

