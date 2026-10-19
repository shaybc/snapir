# GetClientAccountsOp

---
entity_type: operation
entity_id: GetClientAccountsOp
conversion_status: not_started
entry_step: ValidatePin
channel: IVR
host_key: GCAC
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetClientAccounts.xml
source_hash: 9dcc938f33cbdec98354dbeb023d9574ed8f2df9476a13e128ee8f7b171d76dc
---

## Context
- [GetClientAccountsCtxt](contexts/GetClientAccountsCtxt.md)

## Shared Components
- 3 shared components
- format StandardErrorRSFmt: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)
- implClass com.ibm.il.dse.operations.common.ValidateInputFields: [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)
- implClass com.ibm.il.dse.operations.common.MapErrorByValueAlways: [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Operation Attributes
- operationFields: `CHANNEL_ID=IVR`
- writeToLog: `true`

## Steps
- [ValidatePin](opsteps/ValidatePin.md)
- [GetAccounts](opsteps/GetAccounts.md)
- [LogIvrCall](opsteps/LogIvrCall.md)
- [NoAccountsFound](opsteps/NoAccountsFound.md)
- [ValidationFailed](opsteps/ValidationFailed.md)
- [DatabaseError](opsteps/DatabaseError.md)
- [TechnicalError](opsteps/TechnicalError.md)

## Request Format
- [GetClientAccountsIvrRQFmt](formats/GetClientAccountsIvrRQFmt.md)

## Reply Format
- [GetClientAccountsIvrRSFmt](formats/GetClientAccountsIvrRSFmt.md)

## Other Formats
- csErrorReplyFormat: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)

## Java Dependencies
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)
- [com.ibm.il.dse.operations.ivr.db.GetClientAccountsIvrSP](classes/com/ibm/il/dse/operations/ivr/db/GetClientAccountsIvrSP.md)
- [com.ibm.il.dse.operations.ivr.db.LogIvrSession](classes/com/ibm/il/dse/operations/ivr/db/LogIvrSession.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
    m_ValidatePin_58w77j["ValidatePin"] -->|"on0Do"| m_GetAccounts_qlqczg["GetAccounts"]
    m_ValidatePin_58w77j["ValidatePin"] -->|"onOtherDo"| m_ValidationFailed_8zi59y["ValidationFailed"]
    m_GetAccounts_qlqczg["GetAccounts"] -->|"on0Do"| m_LogIvrCall_zne2vz["LogIvrCall"]
    m_GetAccounts_qlqczg["GetAccounts"] -->|"on4Do"| m_NoAccountsFound_zhshy3["NoAccountsFound"]
    m_GetAccounts_qlqczg["GetAccounts"] -->|"on8Do"| m_DatabaseError_1pu6otp["DatabaseError"]
    m_GetAccounts_qlqczg["GetAccounts"] -->|"onOtherDo"| m_TechnicalError_sy098r["TechnicalError"]
    m_LogIvrCall_zne2vz["LogIvrCall"] -->|"on0Do"| m_end_25ln["End"]
    m_LogIvrCall_zne2vz["LogIvrCall"] -->|"onOtherDo"| m_end_25ln["End"]
    m_NoAccountsFound_zhshy3["NoAccountsFound"] -->|"onOtherDo"| m_end_25ln["End"]
    m_NoAccountsFound_zhshy3["NoAccountsFound"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_ValidationFailed_8zi59y["ValidationFailed"] -->|"onOtherDo"| m_end_25ln["End"]
    m_ValidationFailed_8zi59y["ValidationFailed"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_DatabaseError_1pu6otp["DatabaseError"] -->|"onOtherDo"| m_end_25ln["End"]
    m_DatabaseError_1pu6otp["DatabaseError"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_TechnicalError_sy098r["TechnicalError"] -->|"onOtherDo"| m_end_25ln["End"]
    m_TechnicalError_sy098r["TechnicalError"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
```
