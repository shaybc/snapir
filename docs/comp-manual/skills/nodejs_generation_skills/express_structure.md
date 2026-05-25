# Node.js / Express Generation Skill

## Purpose

This skill defines the code structure and separation of concerns rules for generating
Node.js/TypeScript/Express microservices from WSBCC operations. It extends the
language-agnostic rules in `skills/conversion_rules_skill.md`, which must also be
read before generating any Node.js service.

For WSBCC source system knowledge see: `wsbcc_developer_manual_v2.md`

---

## Project Structure

Each generated microservice is a standalone Node.js/TypeScript application:

```
{service-name}/
├── src/
│   ├── index.ts                      ← Express app entry point
│   ├── router.ts                     ← Route declarations only
│   ├── controller/
│   │   └── GetClientLinksController.ts
│   ├── service/
│   │   └── GetClientLinksService.ts
│   ├── repository/
│   │   └── LinkRepository.ts
│   │   └── LinkTypeRepository.ts
│   ├── model/
│   │   ├── request/
│   │   │   └── GetClientLinksRequest.ts
│   │   ├── response/
│   │   │   └── GetClientLinksResponse.ts
│   │   └── domain/
│   │       └── LinkDomain.ts
│   ├── xml/
│   │   └── XmlSerializer.ts          ← xml2js parsing and xmlbuilder2 serialization
│   └── error/
│       ├── DataNotFoundException.ts
│       ├── TechnicalFailureException.ts
│       └── ErrorHandler.ts
├── tests/
├── package.json
├── tsconfig.json
└── Dockerfile
```

Shared components live in a separate shared npm package imported by all services.

---

## Rule 1 — One Class/Interface Per File

Every exported class, interface, type alias, and enum lives in its own `.ts` file.
The filename matches the exported type name exactly.

---

## Rule 2 — Controller: Route Handler Only

The controller function receives the parsed request object, calls the service, and
sends the serialized response. No business logic, no DB access, no XML parsing
beyond what the middleware already handled.

```typescript
// controller/GetClientLinksController.ts
import { Request, Response, NextFunction } from 'express';
import { GetClientLinksService } from '../service/GetClientLinksService';
import { GetClientLinksRequest } from '../model/request/GetClientLinksRequest';

export class GetClientLinksController {
    constructor(private readonly service: GetClientLinksService) {}

    async execute(req: Request, res: Response, next: NextFunction): Promise<void> {
        try {
            const request = req.body as GetClientLinksRequest;
            const response = await this.service.execute(request);
            res.type('application/xml').send(response);
        } catch (err) {
            next(err);
        }
    }
}
```

---

## Rule 3 — Request/Response Interfaces Are Pure Data Shapes

TypeScript interfaces for request and response are plain data shapes — no methods,
no logic, no DB calls.

```typescript
// model/request/GetClientLinksRequest.ts
export interface GetClientLinksRequest {
    clientId: string;
    bankId: string;
}

// model/response/GetClientLinksResponse.ts
export interface GetClientLinksResponse {
    clientId: string;
    links: LinkDto[];
}

// model/response/LinkDto.ts
export interface LinkDto {
    linkId: string;
    description: string;    // pre-populated by service before serialization
    linkDate: string;       // formatted string
}
```

---

## Rule 4 — Service: Owns the Complete Operation Flow

```typescript
// service/GetClientLinksService.ts
import { LinkRepository } from '../repository/LinkRepository';
import { LinkTypeRepository } from '../repository/LinkTypeRepository';
import { DataNotFoundException } from '../error/DataNotFoundException';

export class GetClientLinksService {
    constructor(
        private readonly linkRepo: LinkRepository,
        private readonly linkTypeRepo: LinkTypeRepository
    ) {}

    async execute(request: GetClientLinksRequest): Promise<GetClientLinksResponse> {
        // 1. Validate
        if (!request.clientId) throw new ValidationError('ClientId is required');

        // 2. Fetch (was opStep GetClientLinksSP)
        const links = await this.linkRepo.findByClientIdAndBankId(
            request.clientId, request.bankId);

        if (links.length === 0) throw new DataNotFoundException('10', '0');

        // 3. Enrich (was CCTableFormat in the response fmtDef)
        for (const link of links) {
            link.description = await this.linkTypeRepo.findDescriptionByLinkId(
                link.linkId);
        }

        // 4. Build and return response
        return {
            clientId: request.clientId,
            links: links.map(l => ({
                linkId: l.linkId,
                description: l.description,
                linkDate: formatDate(l.linkDate)
            }))
        };
    }
}
```

---

## Rule 5 — Repository: DB Access Only

```typescript
// repository/LinkRepository.ts
import { Pool } from 'pg';
import { LinkDomain } from '../model/domain/LinkDomain';

export class LinkRepository {
    constructor(private readonly pool: Pool) {}

    async findByClientIdAndBankId(
            clientId: string, bankId: string): Promise<LinkDomain[]> {
        const result = await this.pool.query(
            'SELECT LINK_ID, LINK_DATE FROM CLIENT_LINKS ' +
            'WHERE CLIENT_ID = $1 AND BANK_ID = $2',
            [clientId, bankId]);
        return result.rows.map(row => ({
            linkId: row.link_id,
            linkDate: row.link_date,
            description: ''
        }));
    }
}
```

---

## Rule 6 — XML Handling Is Isolated

All XML parsing and serialization lives in the `xml/` module. Controllers and services
work with typed objects — they never manipulate XML strings.

```typescript
// xml/XmlSerializer.ts
import { parseStringPromise } from 'xml2js';
import { create } from 'xmlbuilder2';

export async function parseRequest(xmlString: string): Promise<GetClientLinksRequest> {
    const parsed = await parseStringPromise(xmlString, { explicitArray: false });
    return {
        clientId: parsed.GetClientLinks.ClientId,
        bankId: parsed.GetClientLinks.BankId
    };
}

export function buildResponse(response: GetClientLinksResponse): string {
    const doc = create({ version: '1.0' })
        .ele('GetClientLinksResponse')
            .ele('ClientId').txt(response.clientId).up();
    response.links.forEach(link => {
        doc.ele('Link')
            .ele('LinkId').txt(link.linkId).up()
            .ele('LinkDescription').txt(link.description).up()
            .ele('LinkDate').txt(link.linkDate).up()
            .up();
    });
    return doc.end({ prettyPrint: false });
}
```

---

## Rule 7 — Error Handling: Typed Error Classes

```typescript
// error/DataNotFoundException.ts
export class DataNotFoundException extends Error {
    constructor(
        public readonly errorCategory: string,
        public readonly errorNumber: string
    ) {
        super(`Data not found [${errorCategory}/${errorNumber}]`);
        this.name = 'DataNotFoundException';
    }
}

// error/ErrorHandler.ts  — Express error middleware
export function errorHandler(err: Error, req: Request,
                              res: Response, next: NextFunction): void {
    if (err instanceof DataNotFoundException) {
        res.status(404).type('application/xml')
           .send(buildErrorXml(err.errorCategory, err.errorNumber));
    } else {
        res.status(500).type('application/xml')
           .send(buildErrorXml('99', '0'));
    }
}
```

---

## Rule 8 — Stateless Request Handlers

No module-level mutable state that is written during request handling. All data flows
through async function parameters and return values.

---

## Rule 9 — Domain Objects Separate From DTOs

```typescript
// model/domain/LinkDomain.ts
export interface LinkDomain {
    linkId: string;
    description: string;
    linkDate: Date;
}
```

Internal domain objects carry typed data between service and repository. Response
DTOs carry formatted string data for serialization. The service performs the mapping.
