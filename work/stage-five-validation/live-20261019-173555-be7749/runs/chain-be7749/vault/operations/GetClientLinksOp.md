# GetClientLinksOp

---
entity_type: operation
entity_id: GetClientLinksOp
conversion_status: not_started
entry_step: GetClientLinks
channel: INTERNET
host_key: GCLN
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientLinks.xml
source_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88
---

## Context
- [GetClientLinksCtxt](contexts/GetClientLinksCtxt.md)

## Shared Components
- 5 shared components
- context GetClientLinksCtxt: [GetClientLinksCtxt](contexts/GetClientLinksCtxt.md)
- format GetClientLinksRQFmt: [GetClientLinksRQFmt](formats/GetClientLinksRQFmt.md)
- format GetClientLinksRSFmt: [GetClientLinksRSFmt](formats/GetClientLinksRSFmt.md)
- format StandardErrorRSFmt: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)
- implClass com.ibm.il.dse.operations.common.MapErrorByValueAlways: [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Operation Attributes
- writeToLog: `false`

## Steps
- [GetClientLinks](opsteps/GetClientLinks.md)
- [NoLinksFound](opsteps/NoLinksFound.md)
- [DatabaseError](opsteps/DatabaseError.md)
- [TechnicalError](opsteps/TechnicalError.md)

## Request Format
- [GetClientLinksRQFmt](formats/GetClientLinksRQFmt.md)

## Reply Format
- [GetClientLinksRSFmt](formats/GetClientLinksRSFmt.md)

## Other Formats
- csErrorReplyFormat: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)

## Java Dependencies
- [com.ibm.il.dse.operations.internet.db.GetClientLinksSP](classes/com/ibm/il/dse/operations/internet/db/GetClientLinksSP.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
    m_GetClientLinks_14paye0["GetClientLinks"] -->|"on0Do"| m_end_25ln["End"]
    m_GetClientLinks_14paye0["GetClientLinks"] -->|"on4Do"| m_NoLinksFound_1ii75ze["NoLinksFound"]
    m_GetClientLinks_14paye0["GetClientLinks"] -->|"on8Do"| m_DatabaseError_1pu6otp["DatabaseError"]
    m_GetClientLinks_14paye0["GetClientLinks"] -->|"onOtherDo"| m_TechnicalError_sy098r["TechnicalError"]
    m_NoLinksFound_1ii75ze["NoLinksFound"] -->|"onOtherDo"| m_end_25ln["End"]
    m_NoLinksFound_1ii75ze["NoLinksFound"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_DatabaseError_1pu6otp["DatabaseError"] -->|"onOtherDo"| m_end_25ln["End"]
    m_DatabaseError_1pu6otp["DatabaseError"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_TechnicalError_sy098r["TechnicalError"] -->|"onOtherDo"| m_end_25ln["End"]
    m_TechnicalError_sy098r["TechnicalError"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
```
