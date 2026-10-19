# com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP
conversion_status: not_started
shared: false
used_by_steps:
  - CheckLimits
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\db\ValidateTransferLimitsSP.java
source_hash: 9d53db5a089f95744959a557e6c43811faa0636cdc8ed9cd26c0e8c9d12fc8bb
---

## Package
- `com.ibm.il.dse.operations.internet.db`

## Behavior Type
- `db_accessor`
- `validator`

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`

## Inheritance
- extends: `com.ibm.dse.base.CCOperationStep`
- implements: none

## Return Codes
- Returns `0` (transfer is within limits and account is eligible; rc success)
- Returns `3` (daily transfer limit would be exceeded; rc limit exceeded)
- Returns `4` (insufficient available funds; rc insufficient)
- Returns `5` (source account not eligible for outgoing transfers; rc not eligible)
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
- `java.math.BigDecimal`
- `java.sql.CallableStatement`
- `java.sql.Connection`
- `java.sql.Types`

## Inferred External Dependencies
- IBM/WAS
- Database
