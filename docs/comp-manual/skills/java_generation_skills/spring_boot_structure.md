# Java / Spring Boot Generation Skill

## Purpose

This skill defines the code structure and separation of concerns rules for generating
Java/Spring Boot microservices from WSBCC operations. It extends the language-agnostic
rules in `skills/conversion_rules_skill.md`, which must also be read before generating
any Java service.

For WSBCC source system knowledge see: `wsbcc_developer_manual_v2.md`

---

## Package Structure

Each generated microservice uses the following package layout. Every package has one
clear responsibility and must not contain classes that belong to another package.

```
com.company.{channel}.{operation_name}/
  controller/     ← HTTP entry point only
  service/        ← Business logic and operation flow
  repository/     ← DB access only
  model/
    request/      ← Inbound JAXB-annotated DTOs
    response/     ← Outbound JAXB-annotated DTOs
    domain/       ← Internal typed objects passed between service and repository
  xml/            ← JAXB configuration and marshaller beans
  error/          ← Typed exception classes and error response builders
```

Shared components across multiple operations live in a separate `common-lib` module:

```
com.company.common/
  model/          ← Shared request/response DTOs (shared fmtDef equivalents)
  repository/     ← Repository classes used by multiple operations
  xml/            ← Shared JAXB configuration
  util/           ← Pure stateless utility methods (no Spring beans, no DB)
  error/          ← Shared exception types and error response structures
```

---

## Rule 1 — One Class Per File

Every class, interface, enum, and record lives in its own `.java` file. The filename
must match the public type name exactly. No nested top-level types.

```
✅ GetClientLinksService.java
✅ GetClientLinksRequest.java
✅ GetClientLinksResponse.java
✅ LinkDto.java
✅ DataNotFoundException.java
❌ GetClientLinks.java  ← contains multiple types
```

---

## Rule 2 — Controller: HTTP Boundary Only

The `@RestController` class is the HTTP boundary. Its only responsibilities are:

- Receive the HTTP request and let Spring/JAXB deserialize the XML body to a request DTO
- Call the service with the deserialized request
- Return the service result as a `ResponseEntity`
- Declare `@ExceptionHandler` methods to map typed exceptions to HTTP status codes

```java
@RestController
@RequestMapping("/api/{channel}")
public class GetClientLinksController {

    private final GetClientLinksService service;

    public GetClientLinksController(GetClientLinksService service) {
        this.service = service;
    }

    @PostMapping(value = "/getClientLinks",
                 consumes = MediaType.APPLICATION_XML_VALUE,
                 produces = MediaType.APPLICATION_XML_VALUE)
    public ResponseEntity<GetClientLinksResponse> execute(
            @RequestBody GetClientLinksRequest request) {
        return ResponseEntity.ok(service.execute(request));
    }

    @ExceptionHandler(DataNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(DataNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse(ex.getErrorCategory(), ex.getErrorNumber()));
    }

    @ExceptionHandler(TechnicalFailureException.class)
    public ResponseEntity<ErrorResponse> handleTechnical(TechnicalFailureException ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse(ex.getErrorCategory(), ex.getErrorNumber()));
    }
}
```

The controller must not contain:
- Any conditional logic beyond exception handling
- Any DB access
- Any field validation
- Any business decisions

---

## Rule 3 — JAXB DTOs Are Pure Data Carriers

Request and response DTO classes contain only:
- `@Xml*` annotations
- Private fields
- No-argument constructor
- Getters and setters

Nothing else. No logic. No DB calls. No validation. No conditional code.

```java
// ✅ Correct request DTO
@XmlRootElement(name = "GetClientLinks")
@XmlAccessorType(XmlAccessType.FIELD)
public class GetClientLinksRequest {

    @XmlElement(name = "ClientId")
    private String clientId;

    @XmlElement(name = "BankId")
    private String bankId;

    public GetClientLinksRequest() {}

    public String getClientId() { return clientId; }
    public void setClientId(String clientId) { this.clientId = clientId; }

    public String getBankId() { return bankId; }
    public void setBankId(String bankId) { this.bankId = bankId; }
}

// ✅ Correct response DTO
@XmlRootElement(name = "GetClientLinksResponse")
@XmlAccessorType(XmlAccessType.FIELD)
public class GetClientLinksResponse {

    @XmlElement(name = "ClientId")
    private String clientId;

    @XmlElementWrapper(name = "Links")
    @XmlElement(name = "Link")
    private List<LinkDto> links;

    public GetClientLinksResponse() {}
    // getters and setters only
}

// ✅ Correct nested DTO
@XmlAccessorType(XmlAccessType.FIELD)
public class LinkDto {

    @XmlElement(name = "LinkId")
    private String linkId;

    @XmlElement(name = "LinkDescription")
    private String description;   // pre-populated by service before serialization

    @XmlElement(name = "LinkDate")
    private String linkDate;      // formatted string — service handles date formatting

    public LinkDto() {}
    // getters and setters only
}
```

---

## Rule 4 — Service: Owns the Complete Operation Flow

The `@Service` class is the direct equivalent of the WSBCC opStep chain plus all the
logic that was spread across opSteps, format processing, and CCTableFormat lookups.

The service receives a request DTO, executes the full business flow, and returns a
response DTO. It must be the only place where:
- Input validation occurs
- Repositories are called
- Business decisions are made
- Domain objects are assembled into response DTOs
- Data enrichment (formerly CCTableFormat DB lookups) occurs

```java
@Service
public class GetClientLinksService {

    private final LinkRepository linkRepository;
    private final LinkTypeRepository linkTypeRepository;

    public GetClientLinksService(LinkRepository linkRepository,
                                  LinkTypeRepository linkTypeRepository) {
        this.linkRepository = linkRepository;
        this.linkTypeRepository = linkTypeRepository;
    }

    public GetClientLinksResponse execute(GetClientLinksRequest request) {
        // 1. Validate input (was implicit in WSBCC unformat)
        validateRequest(request);

        // 2. Fetch (was opStep GetClientLinksSP, RC=4 → DataNotFoundException)
        List<LinkDomain> links = linkRepository
            .findByClientIdAndBankId(request.getClientId(), request.getBankId());

        if (links.isEmpty()) {
            throw new DataNotFoundException("10", "0");
        }

        // 3. Enrich (was CCTableFormat inside the response fmtDef — moved here)
        links.forEach(link ->
            link.setDescription(
                linkTypeRepository.findDescriptionByLinkId(link.getLinkId())));

        // 4. Build response DTO (was csReplyFormat)
        return buildResponse(request.getClientId(), links);
    }

    private void validateRequest(GetClientLinksRequest request) {
        if (request.getClientId() == null || request.getClientId().isBlank()) {
            throw new ValidationException("ClientId is required");
        }
    }

    private GetClientLinksResponse buildResponse(String clientId,
                                                  List<LinkDomain> links) {
        GetClientLinksResponse response = new GetClientLinksResponse();
        response.setClientId(clientId);
        response.setLinks(links.stream()
            .map(this::toLinkDto)
            .collect(Collectors.toList()));
        return response;
    }

    private LinkDto toLinkDto(LinkDomain domain) {
        LinkDto dto = new LinkDto();
        dto.setLinkId(domain.getLinkId());
        dto.setDescription(domain.getDescription());
        dto.setLinkDate(formatDate(domain.getLinkDate()));
        return dto;
    }

    private String formatDate(LocalDate date) {
        return date != null ? date.format(DateTimeFormatter.ofPattern("yyyyMMdd")) : null;
    }
}
```

---

## Rule 5 — Repository: One Responsibility Per Class

Each `@Repository` class performs DB access for one logical entity or one group of
closely related queries. No business logic. No response building. No calls to other
repositories.

```java
@Repository
public class LinkRepository {

    private final JdbcTemplate jdbcTemplate;

    public LinkRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<LinkDomain> findByClientIdAndBankId(String clientId, String bankId) {
        return jdbcTemplate.query(
            "SELECT LINK_ID, LINK_DATE FROM CLIENT_LINKS " +
            "WHERE CLIENT_ID = ? AND BANK_ID = ?",
            (rs, rowNum) -> {
                LinkDomain domain = new LinkDomain();
                domain.setLinkId(rs.getString("LINK_ID"));
                domain.setLinkDate(rs.getDate("LINK_DATE").toLocalDate());
                return domain;
            },
            clientId, bankId);
    }
}

@Repository
public class LinkTypeRepository {

    private final JdbcTemplate jdbcTemplate;

    // This repository encapsulates what was CCTableFormat in the WSBCC fmtDef
    public String findDescriptionByLinkId(String linkId) {
        return jdbcTemplate.queryForObject(
            "SELECT DESCRIPTION FROM LINK_TYPES WHERE KEY = ?",
            String.class, linkId);
    }
}
```

---

## Rule 6 — Error Handling: Typed Exceptions Only

Each distinct business error condition is a typed exception class in the `error/`
package. Never return error codes through method signatures. Never use generic
`RuntimeException` with a message string as the only distinguisher.

```java
// error/DataNotFoundException.java
public class DataNotFoundException extends RuntimeException {
    private final String errorCategory;
    private final String errorNumber;

    public DataNotFoundException(String errorCategory, String errorNumber) {
        super("Data not found [" + errorCategory + "/" + errorNumber + "]");
        this.errorCategory = errorCategory;
        this.errorNumber = errorNumber;
    }

    public String getErrorCategory() { return errorCategory; }
    public String getErrorNumber() { return errorNumber; }
}

// error/TechnicalFailureException.java
public class TechnicalFailureException extends RuntimeException {
    private final String errorCategory;
    private final String errorNumber;
    // same pattern
}

// error/ValidationException.java
public class ValidationException extends RuntimeException {
    public ValidationException(String message) { super(message); }
}

// model/response/ErrorResponse.java  (shared DTO in common-lib)
@XmlRootElement(name = "ErrorResponse")
@XmlAccessorType(XmlAccessType.FIELD)
public class ErrorResponse {
    @XmlElement(name = "ErrorCategory") private String errorCategory;
    @XmlElement(name = "ErrorNumber")   private String errorNumber;

    public ErrorResponse() {}
    public ErrorResponse(String errorCategory, String errorNumber) {
        this.errorCategory = errorCategory;
        this.errorNumber = errorNumber;
    }
    // getters and setters
}
```

---

## Rule 7 — XML Configuration Is Isolated

All JAXB marshaller/unmarshaller configuration lives in the `xml/` package or in Spring
`@Configuration` classes. It is never inline in controller or service methods.

```java
// xml/JaxbConfig.java
@Configuration
public class JaxbConfig {

    @Bean
    public Jaxb2Marshaller marshaller() throws Exception {
        Jaxb2Marshaller marshaller = new Jaxb2Marshaller();
        marshaller.setClassesToBeBound(
            GetClientLinksRequest.class,
            GetClientLinksResponse.class,
            ErrorResponse.class);
        return marshaller;
    }
}
```

---

## Rule 8 — Stateless Services

Every `@Service` and `@Repository` bean must be stateless. All data flows through
method parameters and return values. No instance fields that hold request-scoped data.
No static mutable fields.

```java
// ❌ Wrong — instance field holding request data
@Service
public class GetClientLinksService {
    private String currentClientId;  // NOT OK — shared across threads

    public GetClientLinksResponse execute(GetClientLinksRequest request) {
        this.currentClientId = request.getClientId();  // thread-unsafe
        ...
    }
}

// ✅ Correct — all data flows through method parameters
@Service
public class GetClientLinksService {
    public GetClientLinksResponse execute(GetClientLinksRequest request) {
        String clientId = request.getClientId();  // local variable
        ...
    }
}
```

---

## Rule 9 — Domain Objects Separate From DTOs

Do not use JAXB DTO classes as internal data carriers between service and repository.
Use plain domain objects in the `model/domain/` package for internal data flow. The
service maps domain objects to response DTOs before returning.

This ensures:
- JAXB annotations do not pollute internal domain logic
- The wire format can change independently of the internal data model
- Repository row mappers produce typed domain objects, not XML-annotated DTOs

```java
// model/domain/LinkDomain.java  — internal, no JAXB annotations
public class LinkDomain {
    private String linkId;
    private String description;
    private LocalDate linkDate;
    // getters and setters
}
```

---

## Rule 10 — Spring Boot Project Structure

Each generated microservice is a standalone Spring Boot application with this structure:

```
{service-name}/
├── src/main/java/com/company/{channel}/{operation}/
│   ├── Application.java              ← @SpringBootApplication entry point
│   ├── controller/
│   ├── service/
│   ├── repository/
│   ├── model/
│   │   ├── request/
│   │   ├── response/
│   │   └── domain/
│   ├── xml/
│   └── error/
├── src/main/resources/
│   └── application.properties        ← port, datasource, logging config
├── src/test/java/com/company/{channel}/{operation}/
│   ├── controller/                   ← @WebMvcTest controller tests
│   ├── service/                      ← unit tests with mocked repositories
│   └── repository/                   ← @JdbcTest repository tests
└── pom.xml                           ← Spring Boot parent, common-lib dep, JAXB
```

The `pom.xml` must include:
- `spring-boot-starter-web` — HTTP and JAXB marshalling
- `spring-boot-starter-jdbc` — JdbcTemplate
- `spring-boot-starter-actuator` — health endpoints for OpenShift probes
- `{common-lib-group}:{common-lib-artifact}` — shared components
- Java version 17 minimum
- No IBM, WAS, EJB, or WSBCC dependencies
