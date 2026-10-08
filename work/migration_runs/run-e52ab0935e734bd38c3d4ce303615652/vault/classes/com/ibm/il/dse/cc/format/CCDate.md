# com.ibm.il.dse.cc.format.CCDate

---
entity_type: java_class
entity_id: com.ibm.il.dse.cc.format.CCDate
conversion_status: not_started
shared: false
used_by_steps: []
parent_class: com.ibm.il.dse.cc.format.AbstractFormatElement
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_XML\src\com\ibm\il\dse\cc\format\CCDate.java
source_hash: e63d0cb718572ced0c42cc89c4d3bb3f3162d922d27366769b2be8b8bebdc92a
---

## Package
- `com.ibm.il.dse.cc.format`

## Behavior Type
- `formatter`

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.dse.base.Context`
- `com.ibm.dse.base.Tag`

## Inheritance
- extends: `com.ibm.il.dse.cc.format.AbstractFormatElement`
- implements: none

## Return Codes
- Returns `4` (digit year)

## Thrown Exceptions
- `Exception`
- `UnsupportedOperationException`

## Methods
- `initializeFrom`
- `format`
- `unformat`
- `applyDecorators`
- `removeDecorators`
- `extractElement`

## Setter Methods
- None

## Imports
- `com.ibm.dse.base.Context`
- `com.ibm.dse.base.Tag`
- `java.text.SimpleDateFormat`
- `java.util.Date`

## Inferred External Dependencies
- IBM/WAS
