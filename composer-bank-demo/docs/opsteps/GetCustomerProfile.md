# GetCustomerProfile

---
entity_type: opStep
entity_id: GetCustomerProfile
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetCustomerProfileOp.xml
source_hash: 9a00d7cfe189bcde102fa69ef25ddf0ea67e1d0387832c23fb6a6affef8cc0b9
---

## Parent Operation
- [GetCustomerProfileOp](operations/GetCustomerProfileOp.md)

## Implementation
- [demo.bankcomposer.operations.customers.GetCustomerProfileStep](classes/demo/bankcomposer/operations/customers/GetCustomerProfileStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [GetCustomerProfileNotFound](opsteps/GetCustomerProfileNotFound.md)
- `on5Do` -> [GetCustomerProfileInvalidRequest](opsteps/GetCustomerProfileInvalidRequest.md)
- `onOtherDo` -> [GetCustomerProfileFailed](opsteps/GetCustomerProfileFailed.md)

## Raw Attributes
- entity: `customer-profile`
- id: `GetCustomerProfile`
- implClass: `demo.bankcomposer.operations.customers.GetCustomerProfileStep`
- on0Do: `end`
- on4Do: `GetCustomerProfileNotFound`
- on5Do: `GetCustomerProfileInvalidRequest`
- onOtherDo: `GetCustomerProfileFailed`
- sourceSystem: `crm`
