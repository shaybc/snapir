# com.ibm.il.dse.operations.internet.db.GetAccountDetailsSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.db.GetAccountDetailsSP
conversion_status: not_started
shared: false
used_by_steps:
  - GetDetails
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\db\GetAccountDetailsSP.java
source_hash: 6468b1df9864424487f6dd2fc6b112fc4e7de830717b2adfa7c4fd0cf3a738df
---

## Package
- `com.ibm.il.dse.operations.internet.db`

## Behavior Type
- `db_accessor`

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`

## Inheritance
- extends: `com.ibm.dse.base.CCOperationStep`
- implements: none

## Return Codes
- Returns `0` (account found and details loaded; rc success)
- Returns `4` (account not found; rc not found)
- Returns `5` (client does not have access to this account; rc access denied)
- Returns `8` (database error; rc db error)

## Thrown Exceptions
- `Exception`

## Methods
- `execute`

## Setter Methods
- None

## Imports
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`
- `java.sql.CallableStatement`
- `java.sql.Connection`
- `java.sql.Types`

## Inferred External Dependencies
- IBM/WAS
- Database
