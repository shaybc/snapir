# OverviewValidateLinks

---
entity_type: opStep
entity_id: OverviewValidateLinks
conversion_status: not_started
used_by_operations:
  - GetClientOverviewOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientOverview.xml
source_hash: ded99002c19ffea1f8809b324234983e6d5dafb41ae976a7e89bc2d092703dff
---

## Implementation
- [com.ibm.il.dse.cc.cut.CCComplexOpStep](classes/com/ibm/il/dse/cc/cut/CCComplexOpStep.md)

## Parameters
- opExecuteName: `ValidateClientLinksOp`

## Transitions
- `on0Do` -> [OverviewRefreshLinks](opsteps/OverviewRefreshLinks.md)
- `onOtherDo` -> unresolved `end`

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `OverviewValidateLinks`
- implClass: `com.ibm.il.dse.cc.cut.CCComplexOpStep`
- on0Do: `OverviewRefreshLinks`
- onOtherDo: `end`
- opExecuteName: `ValidateClientLinksOp`
