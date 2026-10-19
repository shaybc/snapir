# ValidateClientLinksOp

---
entity_type: operation
entity_id: ValidateClientLinksOp
conversion_status: not_started
entry_step: ValidateClientLinksFetch
channel: INTERNET
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\ValidateClientLinks.xml
source_hash: ddecb3d2c97fde723b10efb9dca896ff54ee73bf923a1f0343bf31199bbf5076
---

## Context
- [GetClientLinksCtxt](contexts/GetClientLinksCtxt.md)

## Shared Components
- 5 shared components
- context GetClientLinksCtxt: [GetClientLinksCtxt](contexts/GetClientLinksCtxt.md)
- format GetClientLinksRQFmt: [GetClientLinksRQFmt](formats/GetClientLinksRQFmt.md)
- format GetClientLinksRSFmt: [GetClientLinksRSFmt](formats/GetClientLinksRSFmt.md)
- format StandardErrorRSFmt: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)
- implClass com.ibm.il.dse.cc.cut.CCComplexOpStep: [com.ibm.il.dse.cc.cut.CCComplexOpStep](classes/com/ibm/il/dse/cc/cut/CCComplexOpStep.md)

## Steps
- [ValidateClientLinksFetch](opsteps/ValidateClientLinksFetch.md)

## Request Format
- [GetClientLinksRQFmt](formats/GetClientLinksRQFmt.md)

## Reply Format
- [GetClientLinksRSFmt](formats/GetClientLinksRSFmt.md)

## Other Formats
- csErrorReplyFormat: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)

## Java Dependencies
- [com.ibm.il.dse.cc.cut.CCComplexOpStep](classes/com/ibm/il/dse/cc/cut/CCComplexOpStep.md)

## Flow Diagram
```mermaid
graph TD
    m_ValidateClientLinksFetch_mfrh1e["ValidateClientLinksFetch"] -->|"on0Do"| m_end_25ln["End"]
    m_ValidateClientLinksFetch_mfrh1e["ValidateClientLinksFetch"] -->|"onOtherDo"| m_end_25ln["End"]
```
