# Prompt 19 — `ServiceSkeletonGeneratorAgent`

## Context
Stage 5, Step 18. All three plan builders (Prompt 18) exist and are tested.
This is the first LLM agent in Phase 4. It generates structure only — no method bodies.

## Reference
`Implementation_plan_V8.md` section 5 Phase 4 (sub-unit 4).

## Files to create
```
agents/operation_assembly/service_skeleton_generator/
├── __init__.py
└── agent.py
```

## LLM instruction (SKELETON_INSTRUCTION)

```
You are generating a Java Spring Boot service class skeleton.

You receive three plan objects. Generate ONLY the class structure.
Do NOT implement any method bodies. Use:
  throw new UnsupportedOperationException("not yet implemented");
for every method body.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
JAVA_PACKAGE_BASE: {java_package_base}
SPRING_BOOT_VERSION: {spring_boot_version}

ROUTING_PLAN: {routing_plan_json}
CONTEXT_PLAN: {context_plan_json}
SERIALIZATION_PLAN: {serialization_plan_json}

GENERATE:
1. Class declaration:
   @Service
   public class {OperationId}Service { ... }

2. Field declarations (constructor-injected):
   - One repository field per db_lookup in serialization_plan.db_lookups.
   - The context class field: private {ContextClass} ctx;
     (created fresh per execute call, NOT a field — see below)

3. Constructor with @Autowired dependencies.

4. Six method signatures (in this order, no bodies yet):
   a. public {ReplyDtoType} execute(String requestXml) throws Exception
   b. private {RequestDtoType} deserializeRequest(String xml)
   c. private void initializeContext({ContextClass} ctx, {RequestDtoType} req)
   d. private void enrichWithDbLookups({ContextClass} ctx)
   e. private String serializeReply({ReplyDtoType} reply)
   f. private String serializeErrorReply({ErrorReplyDtoType} err)

5. Derive DTO type names from plan:
   RequestDtoType = {OperationId}Request
   ReplyDtoType   = {OperationId}Response
   ErrorReplyDtoType = ErrorResponse  (from common-lib)
   ContextClass   = {ContextId} (from context_plan.context_class)

6. Include correct imports:
   - org.springframework.stereotype.Service
   - All DTO types
   - Repository types (from db_lookups)
   - Context class

IMPORTANT: The context class is instantiated INSIDE execute(), not as a field.
Write: var ctx = new {ContextClass}(); at the start of execute().

Output ONLY the Java source. No explanation. No markdown.
```

## Post-generation
1. Write skeleton to `NATIVE_JAVA_ROOT/{channel}/{operation_id}/Service.java`.
2. Run `javac` immediately.
3. If compile fails: retry with compiler error in prompt.
4. If compiles: store in `native_java_artifacts` with status=converted.
5. Log: "Skeleton compiled successfully for {operation_id}."

## Tests
`tests/test_service_skeleton_generator.py` (mock LLM):
- Generated skeleton compiles with stub bodies.
- Six methods present with correct signatures.
- Constructor injection for db_lookup repositories.
- Context instantiated inside execute(), not as field.
