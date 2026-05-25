
Yes, using an AI agent is a good idea for this task, but only if you structure it as a **tool-assisted documentation pipeline**, not as “let an LLM wander around the repo and summarize things.”

The better method is:

**deterministic code/XML extraction first, AI reasoning second.**

You already have the right foundation in this repo: [composer-mapper](C:/GitHub/shaybc/snapir/composer-mapper/README.md) scans XML, Java, operations, opSteps, formats, contexts, and classes into Markdown. That should be the “facts engine.” Then ADK agents can read those generated facts, inspect selected source files, and produce the deep manual.

So my answer is:

1. **Yes, ADK agents are suitable**, especially because the task is large, multi-step, and benefits from checkpoints.
2. **But do not rely on AI alone.** Use agents to interpret, connect, explain, and critique. Use parsers/tools to extract hard facts.
3. For a one-time manual, a simpler Codex/LLM workflow may be enough. For repeatable migration work, ADK is a very good fit.

A strong process would look like this:

```text
Composer codebase
  -> composer-mapper deterministic scan
  -> generated vault/docs
  -> ADK inventory agents
  -> ADK runtime-model agents
  -> ADK critic/reviewer agents
  -> final WSBCC runtime manual
```

You already have an ADK-oriented design started here: [docs/agent-deep-dive.md](C:/GitHub/shaybc/snapir/docs/agent-deep-dive.md). The important rule in that doc is exactly right: agents should receive explicit task packets and should not freely scan the whole repository.

For your specific Step 1, I would create a smaller ADK pipeline:

```text
RuntimeManualOrchestratorAgent
  1. FrameworkInventoryAgent
  2. TagParserExecutionAgent
  3. ContextLifecycleAgent
  4. OperationFlowAgent
  5. FormatWireModelAgent
  6. RuntimeTraceSynthesizerAgent
  7. ManualCriticAgent
```

Each agent gets a narrow job:

`FrameworkInventoryAgent`
Find the core framework classes: tag parsing, operation loading, tag-to-class mapping, context classes, format classes.

`TagParserExecutionAgent`
Explain exactly how XML tags become Java objects: mapping lookup, class instantiation, reflection setters, child tag handling, `execute()` invocation.

`ContextLifecycleAgent`
Document the shared mutable context: where it is created, how fields are populated, how tags read/write it, and how it survives across opSteps.

`OperationFlowAgent`
Trace how an operation chooses the first opStep, executes it, reads return codes, and jumps to the next step.

`FormatWireModelAgent`
Explain how `fmtDef`, `refFormat`, `dataName`, collections, decorators, dates, numbers, and XML output structure relate.

`RuntimeTraceSynthesizerAgent`
Produce the human manual section: “This is exactly what happens at runtime when WSBCC processes one operation.”

`ManualCriticAgent`
Challenge the manual against source evidence: missing classes, vague claims, unsupported runtime assumptions, unclear return-code behavior.

The output should be a single Markdown file, for example:

```text
docs/comp-manual/wsbcc-runtime-model.md
```

Suggested structure:

```md
# WSBCC Runtime Model

## Executive Summary

## Runtime Objects

## Operation Startup

## XML Tag Parsing

## Tag-to-Class Resolution

## Reflection Attribute Binding

## Child Tag Handling

## Context Lifecycle

## execute() Contract

## Return Code Routing

## opStep Transition Model

## fmtDef to XML Wire Format

## Full Runtime Walkthrough

## Evidence Map

## Known Unknowns

## Migration Implications
```

The key prompt style should force evidence-based writing:

```text
You are documenting the WSBCC runtime model for a manual refactoring from monolith to microservices.

Use only the supplied files and extracted facts.
For every behavioral claim, cite the source file and class/method when possible.
Distinguish:
- confirmed by source
- inferred from pattern
- unresolved / needs human confirmation

Your goal is not to summarize the code. Your goal is to explain the runtime mechanics precisely enough that another engineer can safely convert operations by hand.
```

For implementation, I would do it in this order:

1. Run `composer-mapper` over the real Composer codebase.
2. Generate a fresh documentation vault.
3. Build small ADK tools around:
   - XML parsing
   - Java class/method scanning
   - tag-to-class mapping lookup
   - source file reading
   - Markdown writing
4. Give agents **bounded packets**, not the whole repo.
5. Make the final manual pass through a critic agent.
6. Keep a “Known Unknowns” section rather than letting the AI invent details.

My practical recommendation: start with **one agent plus tools**, not a full multi-agent system. Once the output is useful, split it into the specialist agents above. Multi-agent orchestration is worth it when you want repeatability, review loops, and per-topic ownership; it is overkill for the first draft.

You already have enough scaffolding in this repo to make this work. The next best step would be to create a focused ADK prompt/pipeline specifically for `Step 1: Runtime Model Manual`, using `composer-mapper` as the evidence layer.






--------------
--------------
--------------






For one agent plus tools, I’d build a **small evidence toolkit**. The agent should mostly reason and write; the tools should do deterministic repo work.

The minimum useful set:

**1. `repo_inventory_tool`**
Finds the important files.

Inputs:
```json
{ "root": "C:/path/to/composer" }
```

Returns:
```json
{
  "operation_files": [],
  "opstep_files": [],
  "format_files": [],
  "context_files": [],
  "java_files": [],
  "ini_files": []
}
```

Purpose: stops the agent from blindly scanning the whole repo.

**2. `xml_parser_tool`**
Parses Composer XML into structured data.

Should extract:
- operation name/id
- request/response formats
- context references
- opStep references
- tag names
- tag attributes
- `implClass`
- child tag structure
- source file + line numbers if possible

This is probably the most important tool.

**3. `java_source_scanner_tool`**
Scans Java classes structurally.

Should extract:
- package/class name
- superclass/interfaces
- imports
- fields
- setters
- constructors
- `execute()` method signature
- return-code literals
- context reads/writes if detectable
- reflection-relevant setter names
- source file path

For this task, it does not need perfect semantic analysis. It just needs to give the agent a reliable map.

**4. `tag_mapping_tool`**
Resolves XML tags to Java classes.

Sources:
- `dse.ini`
- XML `implClass`
- naming conventions if your Composer codebase has them

Returns:
```json
{
  "tag": "opStep",
  "java_class": "com.foo.SomeStep",
  "source": "dse.ini",
  "confidence": "confirmed"
}
```

This is essential for explaining “XML tag becomes Java object.”

**5. `operation_trace_tool`**
Builds a single-operation runtime trace.

Given one operation, return:

```json
{
  "operation": "GetAccountBalance",
  "request_format": "...",
  "response_format": "...",
  "context": "...",
  "steps": [
    {
      "step_id": "ValidateRequest",
      "tag": "...",
      "java_class": "...",
      "attributes": {},
      "possible_return_codes": ["0", "1", "-1"],
      "next_steps": {}
    }
  ]
}
```

This tool gives the agent a concrete “one operation at runtime” story.

**6. `format_model_tool`**
Parses `fmtDef` structures.

Should extract:
- format id/name
- XML element names
- `dataName`
- nested structures
- collections/tables
- decorators like nil/null handling
- primitive format tags: string, number, date, boolean, XML, table, etc.
- request/response shape

This is what lets the agent explain the XML wire format mechanically.

**7. `context_model_tool`**
Parses context definitions.

Should extract:
- context name/id
- parent context
- declared fields
- inherited fields
- types if available
- references from operations

The agent needs this to explain the shared mutable state carrier.

**8. `source_excerpt_tool`**
Reads narrow source snippets by file/class/method.

Inputs:
```json
{
  "file": "...",
  "symbol": "execute"
}
```

Returns:
```json
{
  "path": "...",
  "start_line": 42,
  "end_line": 91,
  "text": "..."
}
```

This keeps the agent grounded when writing detailed explanations.

**9. `evidence_writer_tool`**
Writes the final Markdown file and optionally stores intermediate JSON.

Outputs:
- `docs/comp-manual/wsbcc-runtime-model.md`
- `docs/comp-manual/evidence/runtime-inventory.json`
- `docs/comp-manual/evidence/operation-traces/*.json`

This gives you repeatable artifacts instead of only chat output.

My suggested first version would be even smaller:

```text
repo_inventory_tool
xml_parser_tool
java_source_scanner_tool
tag_mapping_tool
operation_trace_tool
format_model_tool
source_excerpt_tool
markdown_writer_tool
```

You can skip `context_model_tool` at first if your XML parser already extracts context definitions.

The main agent’s job should be:

```text
Use the tools to build evidence.
Choose 2-3 representative operations.
Trace them end to end.
Infer the general runtime model.
Write the manual.
Mark every uncertain point as unresolved instead of guessing.
```

Since this repo already has `composer-mapper`, I would not start from zero. I’d extend or wrap the existing mapper code into ADK tools. It already knows how to discover Composer files, parse operations, parse formats, parse contexts, index Java classes, and generate Markdown. That is almost exactly the evidence layer your first agent needs.


