---
name: aice-architecture-model
description: Create, update and show the a-ice C4 architecture model stored in .aice/. Use when the user asks to model, map, diagram, document or show the architecture or a part of it (a flow, a subsystem, the startup sequence), and after code changes that add, remove or rename services, apps, data stores, queues, external integrations, major modules, or calls between them.
---

# a-ice architecture model

a-ice keeps a **C4 model** (Simon Brown's Context, Container, Component levels) as YAML in `.aice/`.
The a-ice VS Code extension draws it as interactive diagrams and reloads whenever these files change,
so the user watches your edits appear live.

One **model** holds every object and connection once. **Diagrams** are views over it, and most are
derived automatically: a Context diagram, plus one diagram for every object that has children.

| File | What it holds | Who writes it |
| --- | --- | --- |
| `.aice/model.yaml` | objects, connections, tag groups | you and the user |
| `.aice/flows/<id>.yaml` | ordered steps over connections (a sequence/use case) | you and the user |
| `.aice/diagrams/<id>.yaml` | positions (`layout:`), or explicit `objects:` (and optional `connections:`) lists for a custom view | a-ice writes layout; you may create custom views |
| `.aice/view.yaml` | what the canvas should show right now | you, when the user asks to see something |
| `.aice/agent/` | this skill, JSON Schemas, the validator | a-ice ("Set Up AI Agents"); do not edit |

JSON Schemas for every file are in `.aice/agent/schemas/`.

## Objects

```yaml
- id: billing-service          # required, lowercase-with-dashes, unique, NEVER change once created
  type: component              # required: actor | system | app | store | component | group
  name: Billing Service        # required, what people call it
  description: Plans, seats and Stripe webhooks   # one plain sentence: what it does, not how
  parent: api                  # the object it lives inside (see levels below)
  external: true               # only for things outside this codebase's control (SaaS, partner APIs)
  icon: stripe                 # optional logo; usually leave out (see Logos below)
  technologies: [TypeScript, Express]
  tags: [billing]              # ids declared under tagGroups (declare new ones there)
  team: Platform
  status: future               # live (default, omit) | future | deprecated | removed
  links: [{ name: Runbook, url: "https://…" }]
  code: ["apps/api/src/billing/**"]   # workspace-relative globs of the code it is made of
```

C4 mapping and nesting rules:

| C4 term | a-ice type | parent |
| --- | --- | --- |
| Person | `actor` | none (always top level) |
| Software system | `system` | none |
| Container (deployable/runnable: web app, service, worker, CLI, function) | `app` | a `system` |
| Container (data: database, cache, queue, bucket) | `store` | a `system` |
| Component (module inside a container) | `component` | an `app` or `store` (or another component) |
| Visual grouping | `group` | any |

External services (Stripe, Sentry, S3 as a service, a partner API) are top-level `system`s with `external: true`.
Databases and queues that this system runs are `store`s inside the system.

### Logos

a-ice shows logos offline: brand logos from the Simple Icons set bundled with the extension, plus the
project's own SVG files in `.aice/icons/<name>.svg`. Usually you set nothing:

- An object whose `name` is a known brand gets its logo (Stripe, Sentry, PostgreSQL, Redis…).
- An `app`, `store` or `component` without one gets the logo of its first known `technologies` entry (Vue, Node.js…).
- A file `.aice/icons/<object id or name>.svg` is used automatically for that object.

Set `icon:` only to choose explicitly: a brand slug (`icon: postgresql`), a file in `.aice/icons/` (`icon: acme-crm`), or `icon: none` to show no logo.
Never download or invent brand logos; if a brand has none, leave it and the canvas shows a monogram.

## Connections

```yaml
- id: billing-stripe        # required, unique, stable
  from: billing-service     # object id
  to: stripe                # object id
  description: Creates payment intents   # verb phrase, business language
  technology: HTTPS          # protocol or mechanism: HTTPS, gRPC, SQL, AMQP, Webhook, function call…
  direction: bidirectional   # omit for one-way (the default)
```

Connect at the **lowest level you know**: `billing-service → stripe`, not `api → stripe`.
a-ice lifts connections automatically, so the higher-level diagrams still show `api → stripe` and
`system → stripe`. Adding the higher-level duplicate as well only creates noise.

## Flows

```yaml
# .aice/flows/checkout.yaml
id: checkout
name: Checkout
description: From the cart to a paid order.
diagram: scope-shop         # diagram to play it on (see diagram ids below); optional
steps:
  - connection: web-api-orders           # a connection id from model.yaml
    description: The web app submits the order
  - connection: orders-stripe
    description: The order service charges the card
  - connection: orders-stripe
    kind: reply                          # the answer travels back along the same connection
    description: Stripe confirms the payment
```

Every step must reference an existing connection. Add the connection to `model.yaml` first if it is missing.

## Diagrams

Derived diagram ids: `context` (top-level objects) and `scope-<objectId>` for every object with children
(`scope-api` shows the inside of `api` plus whatever it talks to). You never need files for these.

For a **focused view of a code section** (for example "the initialization path"), create a custom diagram:

```yaml
# .aice/diagrams/startup.yaml
id: startup
name: Startup sequence
objects: [main, config-loader, plugin-registry, http-server, postgres]   # exactly what to show
```

Connections between the listed objects (and lifted ones below them) appear automatically. To show only some of them, add `connections: [<connection ids>]`; then only those are drawn. Do not write `layout:`.

## Workflows

### Model a part of the code ("model the initialization code in src/boot")

1. Read `.aice/model.yaml` if it exists. If it doesn't, create it starting with `version: 1`, `name:`, `tagGroups: []`, `objects: []`, `connections: []`.
2. Read the code. Find the runnable units (apps), data stores, external services, and the modules (components) inside the part you were asked about. Note who calls whom, through what, and why.
3. Reuse existing objects when they are the same thing. Add only what is missing, nested under the right parent.
4. Link every app and component to its code with `code:` globs.
5. Add connections at the lowest level, with a description and technology.
6. If the request is about a sequence (startup, a request path, a job), write a flow for it.
7. If it is about a section, add a custom diagram listing its objects.
8. Run the validator, fix errors, then write `.aice/view.yaml` to show the result.

### Keep the model in step after a code change

After changing code, compare the change with the model:

- New, removed or renamed service, worker, store, queue, external API, or major module → add, remove (or set `status: removed`), or rename (**change `name`, keep `id`**).
- New or removed call, import across modules, SDK, queue topic, or table access → add or remove the connection.
- Moved code → update `code:` globs.
- A flow whose steps no longer match → update its steps.

Then run the validator. Mention the model changes in your summary to the user.

### Show something ("show me the startup flow", "open the billing component")

Write `.aice/view.yaml`. a-ice opens the canvas and jumps there:

```yaml
diagram: scope-api        # a diagram id, or an object id to open its inside
object: billing-service   # select it (opens its parent's diagram if no diagram is given)
focus: true               # dim everything except its neighbours
flow: checkout            # play a flow instead…
step: 2                   # …starting at this step (1-based)
note: billing review      # free text; change it to re-trigger the same view
```

All fields are optional. Use only ids that exist.

### Validate

```
node .aice/agent/validate.cjs
```

It checks syntax, schema, dangling references, parent cycles, flow steps and code globs that match no file.
Exit code 0 means valid. Fix every error; warnings are worth fixing too.

## Rules

- Never change an existing `id`; diagrams, flows and the user's layout depend on it. Rename with `name`.
- Never delete objects or connections you did not create unless the code they describe is gone. The user may have modelled things by hand.
- Do not edit `layout:` in `.aice/diagrams/*.yaml`, and do not touch `.aice/agent/`.
- Keep descriptions to one plain sentence. No marketing words, no implementation trivia.
- Model what the code shows. Do not invent services, stores or connections without evidence.
- Keep YAML valid: quote strings containing `: `, `#`, or starting with `*`, `&`, `!`, `@`, `[`, `{`.
- Prefer small, reviewable edits to `model.yaml`; keep the existing order and add new items near related ones.

## Complete minimal example

```yaml
version: 1
name: Shop
tagGroups:
  - id: domain
    name: Domain
    tags:
      - { id: payments, name: Payments, color: green }
objects:
  - { id: customer, type: actor, name: Customer, description: Buys things online }
  - { id: shop, type: system, name: Shop, description: Online store }
  - { id: web, type: app, parent: shop, name: Web App, description: Storefront, technologies: [React], code: ["apps/web/**"] }
  - { id: api, type: app, parent: shop, name: Orders API, description: Takes and fulfils orders, technologies: [Node.js, Express], code: ["apps/api/**"] }
  - { id: api-orders, type: component, parent: api, name: Orders, description: Creates and tracks orders, code: ["apps/api/src/orders/**"] }
  - { id: api-payments, type: component, parent: api, name: Payments, description: Charges cards, tags: [payments], code: ["apps/api/src/payments/**"] }
  - { id: db, type: store, parent: shop, name: Orders DB, description: Orders and customers, technologies: [PostgreSQL] }
  - { id: stripe, type: system, external: true, name: Stripe, description: Payment processor, tags: [payments] }
connections:
  - { id: customer-web, from: customer, to: web, description: Browses and orders, technology: HTTPS }
  - { id: web-orders, from: web, to: api-orders, description: Submits orders, technology: HTTPS/JSON }
  - { id: orders-payments, from: api-orders, to: api-payments, description: Requests payment }
  - { id: orders-db, from: api-orders, to: db, description: Stores orders, technology: SQL }
  - { id: payments-stripe, from: api-payments, to: stripe, description: Charges cards, technology: HTTPS }
```
