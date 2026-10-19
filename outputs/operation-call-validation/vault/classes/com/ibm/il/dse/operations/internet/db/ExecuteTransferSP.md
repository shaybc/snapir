# com.ibm.il.dse.operations.internet.db.ExecuteTransferSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.db.ExecuteTransferSP
conversion_status: not_started
shared: false
used_by_steps:
  - ExecuteTransfer
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\db\ExecuteTransferSP.java
source_hash: a2e3037c57693fba711306a9605165ab05b5abcd41dfc9d8169ea99ee38d2bcd
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
- Returns `0` (transfer executed successfully; rc success)
- Returns `6` (rejected by core banking (account rules; rc rejected)
- Returns `7` (duplicate transfer reference (already processed); rc duplicate)
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
