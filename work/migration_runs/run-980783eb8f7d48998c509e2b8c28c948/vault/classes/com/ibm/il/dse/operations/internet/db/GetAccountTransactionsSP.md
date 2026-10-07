# com.ibm.il.dse.operations.internet.db.GetAccountTransactionsSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.db.GetAccountTransactionsSP
conversion_status: not_started
shared: false
used_by_steps:
  - GetTransactions
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\db\GetAccountTransactionsSP.java
source_hash: b8ac688669c736e65040d543d75b6f4da88a6fb8b8686f0d5fd0844c9a742365
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
- Returns `0` (transactions fetched (may be empty list — not an error); rc success)
- Returns `4` (empty result (no transactions in range); rc empty)
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
- `java.sql.*`
- `java.util.ArrayList`
- `java.util.LinkedHashMap`
- `java.util.List`
- `java.util.Map`

## Inferred External Dependencies
- IBM/WAS
- Database
