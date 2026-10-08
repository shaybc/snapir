# com.ibm.il.dse.operations.common.ValidateInputFields

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.common.ValidateInputFields
conversion_status: not_started
shared: true
used_by_steps:
  - ValidateRequest
  - ValidateSession
  - ValidateTransfer
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\common\ValidateInputFields.java
source_hash: 0481dd3f3b2bce30fbfba96d2f23daefc016f076cae0fcbab2ce4f3b1846b07b
---

## Package
- `com.ibm.il.dse.operations.common`

## Behavior Type
- `validator`

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`

## Inheritance
- extends: `com.ibm.dse.base.CCOperationStep`
- implements: none

## Return Codes
- Returns `0` (all required fields are present and non-blank)
- Returns `1` (one or more required fields are missing or blank)

## Thrown Exceptions
- `Exception`

## Methods
- `setRequiredFields`
- `execute`

## Setter Methods
- `setRequiredFields`

## Imports
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`

## Inferred External Dependencies
- IBM/WAS
