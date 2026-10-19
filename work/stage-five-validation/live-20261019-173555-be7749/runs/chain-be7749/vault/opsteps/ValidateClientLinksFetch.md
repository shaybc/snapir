# ValidateClientLinksFetch

---
entity_type: opStep
entity_id: ValidateClientLinksFetch
conversion_status: not_started
used_by_operations:
  - ValidateClientLinksOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\ValidateClientLinks.xml
source_hash: ddecb3d2c97fde723b10efb9dca896ff54ee73bf923a1f0343bf31199bbf5076
---

## Implementation
- [com.ibm.il.dse.cc.cut.CCComplexOpStep](classes/com/ibm/il/dse/cc/cut/CCComplexOpStep.md)

## Parameters
- opExecuteName: `GetClientLinksOp`

## Transitions
- `on0Do` -> unresolved `end`
- `onOtherDo` -> unresolved `end`

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `ValidateClientLinksFetch`
- implClass: `com.ibm.il.dse.cc.cut.CCComplexOpStep`
- on0Do: `end`
- onOtherDo: `end`
- opExecuteName: `GetClientLinksOp`
