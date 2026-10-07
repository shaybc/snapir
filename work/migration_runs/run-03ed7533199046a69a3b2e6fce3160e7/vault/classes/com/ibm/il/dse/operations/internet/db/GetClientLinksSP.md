# com.ibm.il.dse.operations.internet.db.GetClientLinksSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.db.GetClientLinksSP
conversion_status: not_started
shared: false
used_by_steps:
  - GetClientLinks
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\db\GetClientLinksSP.java
source_hash: 3236d23fe5afcbd68284a7bb29a470e440668d66fcea8e8e62b69c4035259fc2
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
- Returns `0` (links found and loaded; rc success)
- Returns `4` (no links configured for this client; rc not found)
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
- `java.sql.ResultSet`
- `java.util.ArrayList`
- `java.util.LinkedHashMap`
- `java.util.List`
- `java.util.Map`

## Inferred External Dependencies
- IBM/WAS
- Database
