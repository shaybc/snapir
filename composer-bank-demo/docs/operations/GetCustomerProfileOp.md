# GetCustomerProfileOp

---
entity_type: operation
entity_id: GetCustomerProfileOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetCustomerProfileOp.xml
source_hash: 9a00d7cfe189bcde102fa69ef25ddf0ea67e1d0387832c23fb6a6affef8cc0b9
---

## Context
- [GetCustomerProfileCtxt](contexts/GetCustomerProfileCtxt.md)

## Steps
- [GetCustomerProfile](opsteps/GetCustomerProfile.md)
- [GetCustomerProfileNotFound](opsteps/GetCustomerProfileNotFound.md)
- [GetCustomerProfileInvalidRequest](opsteps/GetCustomerProfileInvalidRequest.md)
- [GetCustomerProfileFailed](opsteps/GetCustomerProfileFailed.md)

## Formats
- csRequestFormat: [GetCustomerProfileRQFmt](formats/GetCustomerProfileRQFmt.md)
- csReplyFormat: [GetCustomerProfileRSFmt](formats/GetCustomerProfileRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.customers.GetCustomerProfileStep](classes/demo/bankcomposer/operations/customers/GetCustomerProfileStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  GetCustomerProfile -->|on0Do| end
  GetCustomerProfile -->|on4Do| GetCustomerProfileNotFound
  GetCustomerProfile -->|on5Do| GetCustomerProfileInvalidRequest
  GetCustomerProfile -->|onOtherDo| GetCustomerProfileFailed
  GetCustomerProfileNotFound -->|onOtherDo| end
  GetCustomerProfileInvalidRequest -->|onOtherDo| end
  GetCustomerProfileFailed -->|onOtherDo| end
```
