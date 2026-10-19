# GetClientLinks

---
entity_type: opStep
entity_id: GetClientLinks
conversion_status: not_started
used_by_operations:
  - GetClientLinksOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientLinks.xml
source_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88
---

## Implementation
- [com.ibm.il.dse.operations.internet.db.GetClientLinksSP](classes/com/ibm/il/dse/operations/internet/db/GetClientLinksSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [NoLinksFound](opsteps/NoLinksFound.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `GetClientLinks`
- implClass: `com.ibm.il.dse.operations.internet.db.GetClientLinksSP`
- on0Do: `end`
- on4Do: `NoLinksFound`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
