# ADK Tools & Integrations Reference

## Built-in Tools

```python
from google.adk.tools import google_search, built_in_code_execution

agent = LlmAgent(
    name="ResearchAgent",
    tools=[google_search, built_in_code_execution],
)
```

| Tool | Import | Use |
|---|---|---|
| `google_search` | `from google.adk.tools import google_search` | Web search |
| `built_in_code_execution` | `from google.adk.tools import built_in_code_execution` | Run Python code |

---

## FunctionTool (Custom Python Functions)

```python
from google.adk.tools import FunctionTool

def get_weather(city: str, unit: str = "celsius") -> dict:
    """Fetches current weather for a city."""
    # Your implementation here
    return {"city": city, "temp": 22, "unit": unit, "condition": "sunny"}

weather_tool = FunctionTool(func=get_weather)

agent = LlmAgent(
    name="WeatherAgent",
    tools=[weather_tool],
    instruction="Help users check weather. Use get_weather for current conditions.",
)
```

**Best practices:**
- Type-annotate all parameters — ADK uses these to generate the tool schema
- Write clear docstrings — the LLM sees these to understand when/how to call the tool
- Return dicts for structured data; strings for simple responses

---

## MCP Tools (Model Context Protocol)

```python
from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters

# Connect to an MCP server (e.g., filesystem, database, custom)
mcp_tools = MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"],
    )
)

agent = LlmAgent(
    name="FileAgent",
    tools=[mcp_tools],  # All tools from the MCP server become available
)
```

---

## AgentTool (Sub-Agent as Tool)

```python
from google.adk.tools.agent_tool import AgentTool

specialist = LlmAgent(name="Specialist", instruction="Do specialized task X.")

caller = LlmAgent(
    name="Caller",
    tools=[AgentTool(agent=specialist)],
    instruction="Use the Specialist tool when you need task X done.",
)
```

---

## OpenAPI Tools

```python
from google.adk.tools.openapi_tool import OpenAPIToolset

# Auto-generate tools from an OpenAPI spec
api_tools = OpenAPIToolset(
    spec_url="https://api.example.com/openapi.json",
    # or spec_str="<yaml/json string>"
)

agent = LlmAgent(name="APIAgent", tools=[api_tools])
```

---

## LangChain & LlamaIndex Integration

```python
# Wrap a LangChain tool
from google.adk.tools.langchain_tool import LangchainTool
from langchain_community.tools import WikipediaQueryRun

wiki_tool = LangchainTool(tool=WikipediaQueryRun(...))

# Wrap a LlamaIndex tool
from google.adk.tools.llamaindex_tool import LlamaIndexTool
```

---

## Session State Reference

State is the primary way agents share data:

```python
# Writing state from an agent
agent = LlmAgent(output_key="my_output")  # auto-writes LLM response to state

# Reading state in instructions
agent = LlmAgent(instruction="Process this: {my_output}")  # template substitution

# State scopes
# "key"      → session-scoped (persists across turns)
# "temp:key" → turn-scoped (cleared after current invocation)
# "user:key" → user-scoped (persists across sessions for same user)
# "app:key"  → app-scoped (shared across all users)
```

---

## Environment Variables

Required for Gemini models:
```bash
export GOOGLE_API_KEY="your-api-key"
# OR for Vertex AI:
export GOOGLE_CLOUD_PROJECT="your-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI="true"
```

---

## Deployment Quick Reference

```python
# Local dev
runner = Runner(agent=root_agent, app_name="app", session_service=InMemorySessionService())

# Cloud Run / production
from google.adk.sessions import DatabaseSessionService
session_service = DatabaseSessionService(db_url="postgresql://...")

# Vertex AI Agent Engine
# Use `adk deploy agent-engine` CLI command
```
