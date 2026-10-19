# com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP
conversion_status: not_started
shared: false
used_by_steps:
  - GetBalance
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\com\ibm\il\dse\operations\ivr\db\GetAccountBalanceSP.java
source_hash: f59e733ef7bcbfe92c77e1213f242cdd50126058bbde230ce245c2177851ad32
---

## Package
- `com.ibm.il.dse.operations.ivr.db`

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
- Returns `0` (success)
- Returns `4` (not found)
- Returns `8` (db error)

## Thrown Exceptions
- `Exception`

## Methods
- `execute`

## Setter Methods
- None

## Imports
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`
- `java.sql.*`

## Inferred External Dependencies
- IBM/WAS
- Database
