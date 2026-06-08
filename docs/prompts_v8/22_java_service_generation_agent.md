# Prompt 22 — `JavaServiceGenerationAgent` (pilot only)

## Context
Stage 6. All Phase 4 agents (19-21) exist.
This agent generates the complete Spring Boot microservice project from the
assembled native Java service class.

## Reference
`Implementation_plan_V8.md` section 5 Phase 5,
`skills/java_generation_skills/spring_boot_structure.md` — read this in full.

## Files to create
```
agents/java_service_generation/
├── __init__.py
└── agent.py
```

## LLM instruction

```
You are generating a complete Java Spring Boot microservice for a single operation.

You receive a validated native Java service class and must wrap it into a proper
Spring Boot project following all structure and separation-of-concerns rules.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
SERVICE_CLASS_SOURCE: {native_java_service}
JAXB_REQUEST_DTO: {request_dto_source}
JAXB_REPLY_DTO: {reply_dto_source}
JAXB_ERROR_DTO: {error_dto_source}
CONTEXT_CLASS: {context_class_source}
REPOSITORY_INTERFACES: {repository_sources}
JAVA_PACKAGE_BASE: {java_package_base}
SPRING_BOOT_VERSION: {spring_boot_version}
JAVA_VERSION: {java_version}

REQUIRED FILES TO GENERATE:
1. controller/{OperationId}Controller.java
   - @RestController
   - Receives XML body, calls service, returns XML
   - Maps typed exceptions to HTTP status codes
   - NO business logic

2. service/{OperationId}ServiceImpl.java
   - Implements the service logic (refactor native Java class into Spring @Service)
   - Constructor injection for all repositories
   - Calls enrichWithDbLookups before serialization

3. repository/{Entity}Repository.java (one per db_lookup)
   - @Repository
   - JdbcTemplate-based
   - One method per lookup — no business logic

4. xml/JaxbConfig.java
   - @Configuration
   - Jaxb2Marshaller bean registering all DTOs

5. error/GlobalExceptionHandler.java
   - @ControllerAdvice
   - Handles typed exceptions, returns error response XML

6. Application.java
   - @SpringBootApplication entry point

7. src/main/resources/application.properties
   - server.port=8080
   - spring.datasource.*
   - logging config

8. pom.xml
   - spring-boot-starter-web
   - spring-boot-starter-jdbc
   - spring-boot-starter-actuator
   - common-lib dependency
   - Java {java_version}
   - No IBM dependencies

RULES (from spring_boot_structure.md):
- One class per file
- Controller: HTTP boundary only, no business logic
- JAXB classes: pure data carriers, no logic
- Repository: DB access only, no business logic
- All services stateless
- All DTOs in model/ package
- Typed exceptions in error/ package

Output a JSON map: {"relative_file_path": "file_content", ...}
Include EVERY file. No explanation.
```

## Post-generation
1. Parse JSON output.
2. Write all files to `OUTPUT_ROOT/{channel}/{operation_id}/`.
3. Run `mvn compile` on the generated project.
4. If compile fails: retry up to MAX_RETRIES with error.
5. Store in `generated_artifacts` with status=converted.

## Tests
`tests/test_java_service_generation_agent.py` (mock LLM):
- Controller generated with no business logic.
- Repository generated with JdbcTemplate.
- pom.xml contains no IBM dependency.
- mvn compile failure triggers retry.
