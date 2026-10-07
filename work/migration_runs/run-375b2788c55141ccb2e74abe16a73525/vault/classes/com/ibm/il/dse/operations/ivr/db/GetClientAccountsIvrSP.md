# com.ibm.il.dse.operations.ivr.db.GetClientAccountsIvrSP

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.ivr.db.GetClientAccountsIvrSP
conversion_status: not_started
shared: false
used_by_steps: []
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\com\ibm\il\dse\operations\ivr\db\GetClientAccountsIvrSP.java
source_hash: c2fbea5032a597f6b02c1822bbe401aacb1a0696ad1c841bb88f2f5c7be0ed3a
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
- `java.util.ArrayList`
- `java.util.LinkedHashMap`
- `java.util.List`
- `java.util.Map`

## Inferred External Dependencies
- IBM/WAS
- Database
