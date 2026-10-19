# com.ibm.il.dse.operations.internet.db.GetClientAccountsSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.db.GetClientAccountsSP
conversion_status: not_started
shared: false
used_by_steps:
  - GetAccounts
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\db\GetClientAccountsSP.java
source_hash: 109d3ccbac7adc4cf4baeb5227767952517a3d9988bf7204b5eb78901b7489ad
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
- Returns `0` (accounts found and loaded successfully; rc success)
- Returns `4` (no accounts found for this client; rc not found)
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
- `java.sql.ResultSet`
- `java.sql.Types`
- `java.util.ArrayList`
- `java.util.LinkedHashMap`
- `java.util.List`
- `java.util.Map`

## Inferred External Dependencies
- IBM/WAS
- Database
