# LogIvrCall

---
entity_type: opStep
entity_id: LogIvrCall
conversion_status: not_started
onlyFor: IVR
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientAccounts.xml
source_hash: c6d10b4ed4d931e4e2933f6afeb7d68804cec3db9f1e488ea24a74b332d31bb8
---

> **Channel restriction:** this step only runs on channel(s): `IVR`. It is absent from the generated code for all other channels.

## Implementation
- [com.ibm.il.dse.operations.ivr.db.LogIvrSession](classes/com/ibm/il/dse/operations/ivr/db/LogIvrSession.md)

## Parameters
- None

## Transitions
- `on0Do` -> unresolved `end`
- `onOtherDo` -> unresolved `end`

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `LogIvrCall`
- implClass: `com.ibm.il.dse.operations.ivr.db.LogIvrSession`
- on0Do: `end`
- onOtherDo: `end`
- onlyFor: `IVR`
