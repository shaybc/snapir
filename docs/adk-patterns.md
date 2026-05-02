# ADK Multi-Agent Patterns — Code Reference

Detailed examples for all 8 patterns supported in Google ADK.

---

## 1. Sequential Pipeline

**When:** Steps must happen in strict order; each step's output is the next step's input.

**ADK Primitive:** `SequentialAgent`

**Example — Document Processing Pipeline:**
```python
from google.adk.agents import LlmAgent, SequentialAgent

parser_agent = LlmAgent(
    name="ParserAgent",
    model="gemini-2.0-flash",
    instruction="Extract raw text from the document provided. Output only clean text.",
    output_key="raw_text",
)

extractor_agent = LlmAgent(
    name="ExtractorAgent",
    model="gemini-2.0-flash",
    instruction="""
    Given this text: {raw_text}
    Extract structured data as JSON with keys: title, date, authors, key_points.
    """,
    output_key="structured_data",
)

summarizer_agent = LlmAgent(
    name="SummarizerAgent",
    model="gemini-2.0-flash",
    instruction="""
    Given this structured data: {structured_data}
    Write a 3-paragraph executive summary.
    """,
    output_key="final_summary",
)

pipeline = SequentialAgent(
    name="DocumentPipeline",
    sub_agents=[parser_agent, extractor_agent, summarizer_agent],
)
```

**Key points:**
- Use `output_key` to write to `session.state`
- Reference prior outputs in instructions using `{state_key}` template syntax
- All agents share the same `InvocationContext`

---

## 2. Parallel Fan-Out / Gather

**When:** Multiple independent sub-tasks that don't depend on each other and can run concurrently.

**ADK Primitive:** `ParallelAgent`

**Example — Multi-source Research:**
```python
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

news_researcher = LlmAgent(
    name="NewsResearcher",
    model="gemini-2.0-flash",
    instruction="Search for the latest news about: {topic}. Summarize top 5 findings.",
    output_key="news_results",
    tools=[google_search],
)

academic_researcher = LlmAgent(
    name="AcademicResearcher",
    model="gemini-2.0-flash",
    instruction="Find academic papers and research on: {topic}. List key findings.",
    output_key="academic_results",
    tools=[google_search],
)

social_researcher = LlmAgent(
    name="SocialResearcher",
    model="gemini-2.0-flash",
    instruction="Analyze social media sentiment and trends for: {topic}.",
    output_key="social_results",
    tools=[google_search],
)

# All three run in parallel
parallel_research = ParallelAgent(
    name="ParallelResearch",
    sub_agents=[news_researcher, academic_researcher, social_researcher],
)

synthesizer = LlmAgent(
    name="Synthesizer",
    model="gemini-2.0-flash",
    instruction="""
    Synthesize these research findings into a comprehensive report:
    News: {news_results}
    Academic: {academic_results}
    Social: {social_results}
    """,
    output_key="final_report",
)

# Parallel research feeds into synthesis
full_pipeline = SequentialAgent(
    name="ResearchPipeline",
    sub_agents=[parallel_research, synthesizer],
)
```

**Key points:**
- `output_key` names MUST be unique across parallel agents to avoid collisions
- Use a downstream `SequentialAgent` to gather results after parallel execution
- Parallel agents do not communicate with each other directly

---

## 3. Coordinator / Dispatcher Pattern

**When:** The right agent to handle a request depends on content — dynamic routing.

**ADK Primitive:** `LlmAgent` with `sub_agents` (LLM-driven agent transfer)

**Example — Customer Support Router:**
```python
from google.adk.agents import LlmAgent

billing_agent = LlmAgent(
    name="BillingAgent",
    model="gemini-2.0-flash",
    description="Handles billing questions, invoices, payment issues, and subscription changes.",
    instruction="You are a billing specialist. Resolve the customer's billing issue: {customer_query}",
)

technical_agent = LlmAgent(
    name="TechnicalAgent",
    model="gemini-2.0-flash",
    description="Handles technical issues, bugs, setup problems, and API integration questions.",
    instruction="You are a technical support engineer. Solve the technical issue: {customer_query}",
)

general_agent = LlmAgent(
    name="GeneralAgent",
    model="gemini-2.0-flash",
    description="Handles general inquiries, account info, and anything not covered by other specialists.",
    instruction="You are a general support agent. Help with: {customer_query}",
)

# Coordinator routes dynamically based on sub_agent descriptions
coordinator = LlmAgent(
    name="SupportCoordinator",
    model="gemini-2.0-flash",
    description="Routes customer support requests to the appropriate specialist.",
    instruction="""
    You are the support coordinator. Analyze the customer's request and transfer them 
    to the most appropriate specialist agent. Do not answer directly — always delegate.
    Customer query: {customer_query}
    """,
    sub_agents=[billing_agent, technical_agent, general_agent],
)
```

**Key points:**
- Sub-agent `description` is what the LLM coordinator uses to make routing decisions — make them distinctive
- The coordinator LLM uses tool-call-style agent transfer under the hood
- Set `output_key` in sub-agents to capture their responses

---

## 4. Hierarchical Task Decomposition

**When:** A large complex problem needs to be broken into domains, each with their own specialist team.

**Pattern:** Nested LlmAgent trees — coordinators coordinating coordinators.

**Example — E-commerce Operations System:**
```python
# Level 2: Specialist agents
inventory_checker = LlmAgent(name="InventoryChecker", description="Checks stock levels.", ...)
reorder_agent = LlmAgent(name="ReorderAgent", description="Places reorder requests.", ...)
pricing_analyst = LlmAgent(name="PricingAnalyst", description="Analyzes competitive pricing.", ...)
discount_agent = LlmAgent(name="DiscountAgent", description="Applies promotions and discounts.", ...)

# Level 1: Domain coordinators
inventory_coordinator = LlmAgent(
    name="InventoryCoordinator",
    description="Handles all inventory management tasks including stock and reorders.",
    sub_agents=[inventory_checker, reorder_agent],
)

pricing_coordinator = LlmAgent(
    name="PricingCoordinator",
    description="Handles pricing strategy, competitive analysis, and promotions.",
    sub_agents=[pricing_analyst, discount_agent],
)

# Level 0: Root orchestrator
root_orchestrator = LlmAgent(
    name="EcommerceOrchestrator",
    description="Top-level orchestrator for all e-commerce operations.",
    instruction="Analyze the request and delegate to the appropriate department coordinator.",
    sub_agents=[inventory_coordinator, pricing_coordinator],
)
```

---

## 5. Iterative Refinement / Loop Pattern

**When:** Output quality needs to improve over multiple iterations until a condition is met.

**ADK Primitive:** `LoopAgent`

**Example — Code Generation with Testing Loop:**
```python
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools import built_in_code_execution

code_writer = LlmAgent(
    name="CodeWriter",
    model="gemini-2.0-flash",
    instruction="""
    Write Python code for: {task_description}
    If there was previous feedback: {test_feedback}
    Output ONLY executable Python code.
    """,
    output_key="generated_code",
    tools=[built_in_code_execution],
)

code_tester = LlmAgent(
    name="CodeTester",
    model="gemini-2.0-flash",
    instruction="""
    Test this code: {generated_code}
    Run it and check for errors. 
    If it passes all tests, respond with exactly: APPROVED
    Otherwise, describe what needs to be fixed.
    """,
    output_key="test_feedback",
    tools=[built_in_code_execution],
)

# Loop: write → test → (fix if needed) → repeat
refinement_loop = LoopAgent(
    name="CodeRefinementLoop",
    sub_agents=[code_writer, code_tester],
    max_iterations=5,
)
```

**Exit condition:** The `LoopAgent` exits when `max_iterations` is reached OR when any
sub-agent returns `actions.escalate = True` in its response. Configure a critic/checker
agent to set escalate when the quality threshold is met.

---

## 6. Generator-Critic (Review) Pattern

**When:** Need quality assurance — one agent generates, another reviews/validates.

**Pattern:** Two `LlmAgent`s in a `SequentialAgent` (single review) or `LoopAgent` (iterative).

**Example — Content QA:**
```python
from google.adk.agents import LlmAgent, SequentialAgent

content_writer = LlmAgent(
    name="ContentWriter",
    model="gemini-2.0-flash",
    instruction="Write a blog post about: {topic}. Be thorough and engaging.",
    output_key="draft_content",
)

content_critic = LlmAgent(
    name="ContentCritic",
    model="gemini-2.0-flash",
    instruction="""
    Review this content: {draft_content}
    Check for: accuracy, clarity, tone, SEO, grammar.
    Score it 1-10 and provide specific improvement suggestions.
    """,
    output_key="critique",
)

content_reviser = LlmAgent(
    name="ContentReviser",
    model="gemini-2.0-flash",
    instruction="""
    Original draft: {draft_content}
    Critique received: {critique}
    Rewrite the content addressing all critique points. Output the final polished version.
    """,
    output_key="final_content",
)

review_pipeline = SequentialAgent(
    name="ContentReviewPipeline",
    sub_agents=[content_writer, content_critic, content_reviser],
)
```

---

## 7. Human-in-the-Loop Pattern

**When:** A decision or action requires human approval before proceeding.

**Pattern:** Use an `LlmAgent` with a `FunctionTool` that pauses and requests input,
or use ADK's callback hooks.

**Example — Approval Gate:**
```python
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

def request_human_approval(action_description: str, risk_level: str) -> str:
    """
    Pauses execution and requests human approval.
    In production: sends notification, awaits async response.
    Returns: 'approved' | 'rejected' | 'modified: <new_instruction>'
    """
    print(f"\n⚠️  APPROVAL REQUIRED [{risk_level}]: {action_description}")
    decision = input("Enter 'approve', 'reject', or 'modify: <instruction>': ")
    return decision

approval_tool = FunctionTool(func=request_human_approval)

action_planner = LlmAgent(
    name="ActionPlanner",
    model="gemini-2.0-flash",
    instruction="Plan the actions needed to complete: {task}. List steps clearly.",
    output_key="action_plan",
)

approval_agent = LlmAgent(
    name="ApprovalGateAgent",
    model="gemini-2.0-flash",
    instruction="""
    Review this action plan: {action_plan}
    Identify any high-risk actions and request human approval for them.
    Only proceed if approved.
    """,
    tools=[approval_tool],
    output_key="approval_status",
)

executor = LlmAgent(
    name="ExecutorAgent",
    model="gemini-2.0-flash",
    instruction="""
    Execute the approved action plan: {action_plan}
    Approval status: {approval_status}
    Only execute if status is 'approved'.
    """,
)

human_gated_pipeline = SequentialAgent(
    name="HumanGatedPipeline",
    sub_agents=[action_planner, approval_agent, executor],
)
```

---

## 8. Agent-as-Tool Pattern

**When:** You want to call a sub-agent like a function and use its return value inline.

**ADK Primitive:** `AgentTool`

```python
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

# This agent does one focused job and returns a value
fact_checker = LlmAgent(
    name="FactChecker",
    model="gemini-2.0-flash",
    instruction="Verify if this claim is factually accurate: {claim}. Return: TRUE, FALSE, or UNCERTAIN with reasoning.",
)

# Calling agent uses fact_checker as a tool
journalist_agent = LlmAgent(
    name="JournalistAgent",
    model="gemini-2.0-flash",
    instruction="""
    You are a journalist writing an article about: {topic}
    Use the fact_checker tool to verify any claims before including them.
    Write a verified, accurate article.
    """,
    tools=[AgentTool(agent=fact_checker)],
)
```

---

## Combining Patterns

Real systems mix patterns. A common production architecture:

```
Root LlmAgent (Coordinator/Dispatcher)
├── SequentialAgent (Pipeline A)
│   ├── ParallelAgent (Fan-Out)
│   │   ├── LlmAgent (Worker 1)
│   │   └── LlmAgent (Worker 2)
│   └── LlmAgent (Synthesizer)
└── LoopAgent (Refinement B)
    ├── LlmAgent (Generator)
    └── LlmAgent (Critic)
```

The root dispatcher decides which pipeline to run based on the incoming request.
