# Python / FastAPI Generation Skill

## Purpose

This skill defines the code structure and separation of concerns rules for generating
Python/FastAPI microservices from WSBCC operations. It extends the language-agnostic
rules in `skills/conversion_rules_skill.md`, which must also be read before generating
any Python service.

For WSBCC source system knowledge see: `wsbcc_developer_manual_v2.md`

---

## Project Structure

Each generated microservice is a standalone Python/FastAPI application:

```
{service-name}/
├── app/
│   ├── main.py                        ← FastAPI app entry point
│   ├── router.py                      ← Route declarations only
│   ├── controller/
│   │   └── get_client_links_controller.py
│   ├── service/
│   │   └── get_client_links_service.py
│   ├── repository/
│   │   └── link_repository.py
│   │   └── link_type_repository.py
│   ├── model/
│   │   ├── request/
│   │   │   └── get_client_links_request.py
│   │   ├── response/
│   │   │   └── get_client_links_response.py
│   │   └── domain/
│   │       └── link_domain.py
│   ├── xml/
│   │   └── xml_serializer.py          ← lxml parsing and building
│   └── error/
│       ├── exceptions.py
│       └── error_handlers.py
├── tests/
├── requirements.txt
└── Dockerfile
```

Shared components live in a separate shared Python package installed as a dependency.

---

## Rule 1 — One Class Per Module

Each Python module (`.py` file) contains one primary class or one cohesive group of
closely related functions. Module names use `snake_case`. Class names use `PascalCase`.

---

## Rule 2 — Router/Controller: HTTP Boundary Only

```python
# controller/get_client_links_controller.py
from fastapi import APIRouter, Depends, Response
from app.service.get_client_links_service import GetClientLinksService
from app.model.request.get_client_links_request import GetClientLinksRequest
from app.xml.xml_serializer import parse_request, build_response

router = APIRouter()

@router.post("/getClientLinks",
             response_class=Response,
             media_type="application/xml")
async def execute(
        body: bytes = Depends(raw_xml_body),
        service: GetClientLinksService = Depends(get_service)):
    request = parse_request(body)
    result = await service.execute(request)
    return Response(content=build_response(result), media_type="application/xml")
```

The route function must not contain business logic, DB access, or XML manipulation
beyond delegating to the xml module and service.

---

## Rule 3 — Request/Response Models Are Pure Data Containers

Use Pydantic models for request and response shapes. No logic, no DB calls,
no validation beyond field type declarations.

```python
# model/request/get_client_links_request.py
from pydantic import BaseModel

class GetClientLinksRequest(BaseModel):
    client_id: str
    bank_id: str

# model/response/get_client_links_response.py
from pydantic import BaseModel
from typing import List

class LinkDto(BaseModel):
    link_id: str
    description: str      # pre-populated by service before serialization
    link_date: str        # formatted string

class GetClientLinksResponse(BaseModel):
    client_id: str
    links: List[LinkDto]
```

---

## Rule 4 — Service: Owns the Complete Operation Flow

```python
# service/get_client_links_service.py
from app.repository.link_repository import LinkRepository
from app.repository.link_type_repository import LinkTypeRepository
from app.error.exceptions import DataNotFoundException, ValidationError
from app.model.request.get_client_links_request import GetClientLinksRequest
from app.model.response.get_client_links_response import GetClientLinksResponse, LinkDto
from datetime import date

class GetClientLinksService:

    def __init__(self,
                 link_repo: LinkRepository,
                 link_type_repo: LinkTypeRepository):
        self._link_repo = link_repo
        self._link_type_repo = link_type_repo

    async def execute(self,
                      request: GetClientLinksRequest) -> GetClientLinksResponse:
        # 1. Validate
        if not request.client_id:
            raise ValidationError("client_id is required")

        # 2. Fetch (was opStep GetClientLinksSP)
        links = await self._link_repo.find_by_client_and_bank(
            request.client_id, request.bank_id)

        if not links:
            raise DataNotFoundException("10", "0")

        # 3. Enrich (was CCTableFormat in the response fmtDef)
        for link in links:
            link.description = await self._link_type_repo.find_description(
                link.link_id)

        # 4. Build and return response
        return GetClientLinksResponse(
            client_id=request.client_id,
            links=[
                LinkDto(
                    link_id=l.link_id,
                    description=l.description,
                    link_date=l.link_date.strftime("%Y%m%d")
                )
                for l in links
            ]
        )
```

---

## Rule 5 — Repository: DB Access Only

```python
# repository/link_repository.py
from databases import Database
from app.model.domain.link_domain import LinkDomain
from typing import List

class LinkRepository:

    def __init__(self, db: Database):
        self._db = db

    async def find_by_client_and_bank(self,
                                       client_id: str,
                                       bank_id: str) -> List[LinkDomain]:
        rows = await self._db.fetch_all(
            "SELECT LINK_ID, LINK_DATE FROM CLIENT_LINKS "
            "WHERE CLIENT_ID = :client_id AND BANK_ID = :bank_id",
            {"client_id": client_id, "bank_id": bank_id})
        return [LinkDomain(link_id=r["LINK_ID"],
                           link_date=r["LINK_DATE"],
                           description="")
                for r in rows]
```

---

## Rule 6 — XML Handling Is Isolated

```python
# xml/xml_serializer.py
from lxml import etree
from app.model.request.get_client_links_request import GetClientLinksRequest
from app.model.response.get_client_links_response import GetClientLinksResponse

def parse_request(xml_bytes: bytes) -> GetClientLinksRequest:
    root = etree.fromstring(xml_bytes)
    return GetClientLinksRequest(
        client_id=root.findtext("ClientId") or "",
        bank_id=root.findtext("BankId") or ""
    )

def build_response(response: GetClientLinksResponse) -> bytes:
    root = etree.Element("GetClientLinksResponse")
    etree.SubElement(root, "ClientId").text = response.client_id
    for link in response.links:
        link_el = etree.SubElement(root, "Link")
        etree.SubElement(link_el, "LinkId").text = link.link_id
        etree.SubElement(link_el, "LinkDescription").text = link.description
        etree.SubElement(link_el, "LinkDate").text = link.link_date
    return etree.tostring(root, xml_declaration=True,
                          encoding="UTF-8", pretty_print=False)
```

---

## Rule 7 — Error Handling: Typed Exceptions

```python
# error/exceptions.py
class DataNotFoundException(Exception):
    def __init__(self, error_category: str, error_number: str):
        self.error_category = error_category
        self.error_number = error_number
        super().__init__(f"Not found [{error_category}/{error_number}]")

class TechnicalFailureException(Exception):
    def __init__(self, error_category: str, error_number: str):
        self.error_category = error_category
        self.error_number = error_number

class ValidationError(Exception):
    pass

# error/error_handlers.py
from fastapi import Request
from fastapi.responses import Response
from lxml import etree

async def data_not_found_handler(request: Request,
                                  exc: DataNotFoundException) -> Response:
    return Response(content=_build_error_xml(exc.error_category, exc.error_number),
                    status_code=404, media_type="application/xml")

async def technical_error_handler(request: Request,
                                   exc: TechnicalFailureException) -> Response:
    return Response(content=_build_error_xml(exc.error_category, exc.error_number),
                    status_code=500, media_type="application/xml")

def _build_error_xml(category: str, number: str) -> bytes:
    root = etree.Element("ErrorResponse")
    etree.SubElement(root, "ErrorCategory").text = category
    etree.SubElement(root, "ErrorNumber").text = number
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
```

---

## Rule 8 — Stateless Async Services

All service and repository methods are `async`. No instance-level mutable state written
during request handling. All data flows through function parameters and return values.

---

## Rule 9 — Domain Objects Separate From API Models

```python
# model/domain/link_domain.py
from dataclasses import dataclass
from datetime import date

@dataclass
class LinkDomain:
    link_id: str
    description: str
    link_date: date
```

Domain objects are plain dataclasses with Python native types. API response models
contain formatted strings for serialization. The service performs the mapping.

---

## Rule 10 — Project Dependencies

`requirements.txt` must include:
- `fastapi` — web framework
- `uvicorn` — ASGI server
- `lxml` — XML parsing and building
- `pydantic` — data validation
- `databases` + appropriate driver (`asyncpg` for PostgreSQL, `aiomysql` for MySQL)
- `{shared-package}` — shared common components

Must not include any IBM, WAS, EJB, or WSBCC packages.
