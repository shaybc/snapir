---
name: aice-architecture-model
description: Create, update and show the a-ice C4 architecture model stored in .aice/, built as zoomable levels (system → apps and stores → components). Use when the user asks to model, map, diagram, document or show the architecture or a part of it (a flow, a subsystem, the startup sequence), and after code changes that add, remove or rename services, apps, data stores, queues, external integrations, major modules, or calls between them.
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
| `.aice/edited.json` | snapshot of the person's edited values, used by the validator | a-ice; do not edit |

JSON Schemas for every file are in `.aice/agent/schemas/`.

## Build the model in levels (read this first)

The whole point of a-ice is that the user starts with **one simple overview** and **zooms in**
(double-click) to see more detail, level by level. Every object with children becomes a diagram of its own.
So the model must be a **tree**, not a flat list. A model where everything sits on one level is wrong,
even if every object and connection in it is correct.

| Level | Diagram | Shows | Typical size |
| --- | --- | --- | --- |
| 1 Context | `context` | people (`actor`), **this codebase as one `system`** (rarely 2–3), and external systems | 1 internal system, 2–10 others |
| 2 App | `scope-<system>` | the system's runnable units (`app`) and data stores (`store`) | 2–10 |
| 3 Component | `scope-<app>` | the main modules inside one app (`component`) | 3–12 per app |
| 4 Sub-component | `scope-<component>` | the parts of a big component, when it is worth explaining | 3–10, optional |

**Level 4 is the deepest level.** C4 has four levels, and its fourth (code) level is not drawn by hand.
Never put an object at level 5 or deeper: no component inside a component inside a component.

**Work top-down, one level at a time, and finish each level before going deeper:**

1. **Level 1.** Create one `system` for the codebase (named after the product), the actors who use it,
   and the external systems it talks to. Nothing else goes at the top level.
2. **Level 2.** Inside the system (`parent: <system id>`), add one `app` per thing that is built,
   deployed or started on its own (web front end, API server, worker, CLI, mobile app, serverless
   function group, desktop app, VS Code extension host…), and one `store` per database, cache, queue or bucket
   that the system owns. **A single-program repository still has one `app`**: the system contains that app,
   and the app contains the components. Do not skip this level.
3. **Level 3.** Inside each app (`parent: <app id>`), add its main modules as `component`s: the folders or
   packages that own a responsibility (routing, auth, billing, rendering, persistence…). Aim for 3–12.
   Leave out plumbing (utils, helpers, types, constants, config) unless it is a real subsystem.
4. **Level 4 (optional, and the last).** When a component is large or is the subject of the user's question, give it
   sub-components (`parent: <component id>`), again 3–10. Sub-components have **no children**: anything
   finer (classes, functions, steps inside a module, the folder structure below it) goes into the
   sub-component's `details` (Markdown, as long as needed) and its `code:` globs, not into more boxes.
   Do not mirror the folder tree: a deep folder hierarchy is still one component with good `details`.
5. **Connections** go between the most specific objects you know (component → component, component → store,
   component → external system). a-ice lifts them for the higher levels, so do not also add app → app or
   system → system duplicates.

**How to decide a level.** Ask "would this be explained on the overview slide?" If yes, it is level 1;
"is it started, deployed or scaled on its own?" → `app`; "does it store data?" → `store`;
"is it a part of an app?" → `component`. When a level would have more than ~15 objects, group them under
a new parent one level down instead of listing them side by side.

**Self-check before you finish** (the validator warns about each of these):

- The Context diagram has no `app`, `store` or `component`, only actors and systems.
- Every `app` and `store` has a `system` parent; every `component` has an `app`, `store` or `component` parent.
- Your own system has children (it can be zoomed into), and each app with real code has components.
- No parent has more than ~15 direct children.
- Nothing is deeper than level 4 (system → app → component → sub-component).
- No object carries its children's tags, and no object has more than 3 tags (see "Tags").

**Wrong (flat)** — every module at the top level, nothing to zoom into:

```yaml
objects:
  - { id: router, type: component, name: Router }
  - { id: auth, type: component, name: Auth }
  - { id: billing, type: component, name: Billing }
  - { id: db, type: store, name: Database }
  # …20 more siblings
```

**Right (layered)** — the overview shows one system; zooming in reveals the app and store; zooming into the app reveals its modules:

```yaml
objects:
  - { id: shop, type: system, name: Shop }                       # level 1
  - { id: api, type: app, parent: shop, name: API }              # level 2
  - { id: db, type: store, parent: shop, name: Database }        # level 2
  - { id: router, type: component, parent: api, name: Router }   # level 3
  - { id: auth, type: component, parent: api, name: Auth }       # level 3
  - { id: billing, type: component, parent: api, name: Billing } # level 3
  - { id: billing-plans, type: component, parent: billing, name: Plans }     # level 4, optional
```

## Tags

Tags mark **cross-cutting concerns** that the boxes do not already show: a domain (billing, growth),
a quality (public API, PII, deprecated path), an ownership or a region. People use them to light up and
filter the diagrams.

- **Tag an object only for what is true of that object itself**, at its own level. Never copy the tags of
  its children onto it: when someone hovers a tag, a-ice already lights up the system or app that contains
  a tagged component. A system tagged with every tag used inside it carries no information.
- **At most 3 tags per object**, usually 0–2. Many objects need none.
- **Do not repeat the structure.** If a tag would mark one object and the things inside it (a "stage" or
  "module" tag for each component), leave it out: the component already shows that. A tag should cut
  across different parents.
- Declare each tag once under `tagGroups`, in a group named for what it describes (Domain, Quality,
  Region…), and remove tags nobody uses.

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
  team: Platform               # or several: [Platform, Payments]
  status: future               # live (default, omit) | future | deprecated | removed
  links: [{ name: Runbook, url: "https://…" }]
  code: ["apps/api/src/billing/**"]   # workspace-relative globs of the code it is made of
  details: |                   # optional long-form documentation in Markdown, any length
    ## Responsibilities
    - Owns plans and seats; never charges cards itself
    ## How it works
    Webhooks are verified, then queued. See `billing/webhooks.ts`.
```

`description` is the one sentence shown on the card. `details` (objects, connections and flows) is where longer
documentation goes: responsibilities, key decisions, data it owns, failure modes, runbooks, links. Use Markdown
(`##` headings, lists, `code`, links) and a YAML block scalar (`details: |`). Write it when the user asks you to
document something, or when you learn something non-obvious from the code; never put long text in `description`.

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
details: |                  # optional, Markdown: preconditions, edge cases, links
  Runs for guests and signed-in users. Retries the charge once on a timeout.
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

## Respect the person's edits

People customise the model in a-ice: they rename objects, rewrite descriptions, write long `details`,
add tags and links, and move objects to other levels. a-ice records which fields a person edited:

```yaml
- id: billing-service
  name: Billing                     # the person renamed it
  description: Plans, seats and invoices
  edited: [name, description, details, tags]   # written by a-ice, never by you
```

The person's edits are kept **while they are true**. They are never a reason to keep something stale.

Rules:

1. **Do not reword an edited field for style.** If it is still true, leave it exactly as it is, even if you
   would phrase it differently.
2. **Correct it when the code made it wrong.** When the thing it describes changed (renamed in the code,
   re-implemented, a connection that moved from HTTP to a message queue, a responsibility that moved
   elsewhere), fix the parts that are now wrong and keep the rest of the person's text and style. List each
   correction in your summary ("Billing → Payments: the connection is now MQ, not HTTP; I updated your description").
3. **Moving is not replacing.** When the same thing only moves (to another parent while restructuring into
   levels, or another folder), keep its `id` so positions, flows and connections follow it, and keep its fields.
4. **A replacement starts fresh.** When an object is replaced by a different one (split, merged, rewritten as
   something else), delete the old object together with the person's details, tags and wording about it,
   create the new one from the code, and point connections and flow steps at it. Do not copy the old
   customisations onto it. Report what was dropped ("Replaced Billing Worker with Billing Jobs; your details for
   Billing Worker were removed").
5. **Delete what is wrong or gone, for real.** When the code an object stands for no longer exists, or the
   object is simply wrong, delete it (and its connections), even if a person customised it. Do not keep it
   with a status. Then **list every deleted object that had `edited:` in your summary**, by name, with the
   reason ("Deleted Billing Worker — you had written its details; apps/worker was removed").
6. **Never add to or clear `edited:`.** It only records what people changed. Do not edit `edited.json`.
7. **Run the validator.** It compares the model with `edited.json` and adds a *note* for everything a person
   wrote that you changed or deleted. Each note must be explained in your summary; put back anything you
   changed without a reason in the code.

## Workflows

### Model a part of the code ("model the initialization code in src/boot")

1. Read `.aice/model.yaml` if it exists. If it doesn't, create it starting with `version: 1`, `name:`, `tagGroups: []`, `objects: []`, `connections: []`.
2. Read the code. Find the runnable units (apps), data stores, external services, and the modules (components) inside the part you were asked about. Note who calls whom, through what, and why.
3. Place everything in the tree described in "Build the model in levels": system at the top, apps and stores inside it, components inside apps. When the model is new, build level 1, then level 2, then level 3, rather than listing everything at once.
4. Reuse existing objects when they are the same thing. Add only what is missing, nested under the right parent.
5. Link every app and component to its code with `code:` globs.
6. Add connections at the lowest level, with a description and technology.
7. If the request is about a sequence (startup, a request path, a job), write a flow for it.
8. If it is about a section, add a custom diagram listing its objects.
9. Write the narrated tour for every diagram and flow you created or changed (see "Narrated tours").
10. Run the validator. Fix every error **and every layering warning** (flat model, missing parent, too many objects on one level) before you finish.
11. Write `.aice/view.yaml` to show the result: usually `diagram: context` for a new model, so the user starts at the overview and zooms in.

### Keep the model in step after a code change

After changing code, compare the change with the model:

- New, removed or renamed service, worker, store, queue, external API, or major module → add, remove (or set `status: removed`), or rename (**change `name`, keep `id`**).
- New or removed call, import across modules, SDK, queue topic, or table access → add or remove the connection.
- Moved code → update `code:` globs.
- A flow whose steps no longer match → update its steps.
- A diagram or flow whose content changed → update its `narration:` (new stops, changed meaning, removed stops), leaving the person's entries alone.

Then run the validator. Mention the model changes in your summary to the user.

### Narrated tours

a-ice can walk the user through any diagram or flow: it pans and zooms to each stop, shows the narrator's
text and reads it aloud. Without your text it uses generic sentences built from names and descriptions.
**Write the narration yourself**, the way a senior engineer would explain the system to a new colleague.

**1. List the stops.** The tour's order and keys come from a-ice, not from you:

```
node .aice/agent/validate.cjs --tour scope-api      # one diagram or flow
node .aice/agent/validate.cjs --tour                # all of them
```

Each line shows a key, who wrote the current text (`generated`, `written`, or `person, keep`), and the text.
Keys: `intro`, `outro`, `o:<objectId>` (an object), `e:<from>-><to>` (a connection, using the two
objects **as drawn on that diagram**, so on the Context diagram a call from a component inside your system
is `e:<system>-><other>`), and `s:<index>` for flow steps (counted from 0).

**2. Write `narration:`** in the diagram file (`.aice/diagrams/<id>.yaml`; create it with just `id:` and
`scope:` when it does not exist, and never add `layout:`) or in the flow file:

```yaml
id: scope-api
scope: api
narration:
  intro: Inside the API there are four parts. Requests come in through the router, and everything else hangs off it.
  o:http-router: The HTTP router is the front door. It checks who you are and passes each request to the right service.
  e:http-router->billing-service: Anything to do with plans or seats goes to the billing service.
  outro: That's the API. Billing is the most involved part; open it to see how plans and webhooks work.
```

**How to write it:**

- Spoken English: 1–3 short sentences per stop, plain words, no Markdown, no lists, no code. It is read aloud.
- Explain **why and how it fits**, not only what it is: what this part is for, what would break without it,
  what the user should notice. Do not just repeat the name and type; the card already shows them.
- The tour follows the order `--tour` prints. Use light transitions ("From there…", "Back at the router…"),
  but each stop should still make sense if someone jumps straight to it.
- Always write `intro` (what this diagram or flow is about, and where to look first) and `outro`
  (the takeaway, and what to open next). Then write the objects and connections that matter; it is fine to
  leave obvious stops to the generated text.
- For flows, tell the story of the request: what the user does, what each step achieves, and where it can fail.
- Use only facts from the code and the model. Keep names exactly as in the model.

**3. The person's wording, while it is true.** Keys listed in `narrationEdited:` were written by the person
in a-ice. Do not reword them for style. When a stop is gone (its object, connection or step was deleted or
replaced), remove its entry, the person's included, and remove the key from `narrationEdited:`. When the
stop still exists but the person's text is now wrong (a different protocol, a moved responsibility), correct
the wrong part and keep the rest. Report both in your summary. The validator warns about entries left for
stops that no longer exist.

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
- Never delete objects or connections you did not create unless the code they describe is gone or they are wrong. The user may have modelled things by hand. When you do delete something the person edited, say so in your summary.
- Do not edit `layout:` in `.aice/diagrams/*.yaml`, and do not touch `.aice/agent/`.
- Narration entries whose key is in `narrationEdited:` are the person's: do not reword them for style, but remove them when their stop is gone (and the key from `narrationEdited:`), and correct them when the code made them wrong. Report both. Other narration entries are yours to write, update and remove (see "Narrated tours").
- Keep descriptions to one plain sentence. No marketing words, no implementation trivia. Longer documentation goes in `details:` (Markdown).
- Model what the code shows. Do not invent services, stores or connections without evidence.
- Never flatten: a new model always has a system at the top with apps inside it and components inside the apps.
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
