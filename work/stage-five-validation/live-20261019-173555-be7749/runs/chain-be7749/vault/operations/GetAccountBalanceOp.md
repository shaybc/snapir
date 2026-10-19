# GetAccountBalanceOp

---
entity_type: operation
entity_id: GetAccountBalanceOp
conversion_status: not_started
entry_step: ValidateRequest
channel: IVR
host_key: GBAL
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetAccountBalance.xml
source_hash: 0fb403fd7c6dea2ff8390f4079959769b0e3c15a2c3538965bbb50b481dd4c2e
---

## Context
- [GetAccountBalanceCtxt](contexts/GetAccountBalanceCtxt.md)

## Shared Components
- 3 shared components
- format StandardErrorRSFmt: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)
- implClass com.ibm.il.dse.operations.common.ValidateInputFields: [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)
- implClass com.ibm.il.dse.operations.common.MapErrorByValueAlways: [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Operation Attributes
- operationFields: `CHANNEL_ID=IVR`

## Steps
- [ValidateRequest](opsteps/ValidateRequest.md)
- [GetBalance](opsteps/GetBalance.md)
- [LogIvrCall](opsteps/LogIvrCall.md)
- [AccountNotFound](opsteps/AccountNotFound.md)
- [ValidationFailed](opsteps/ValidationFailed.md)
- [DatabaseError](opsteps/DatabaseError.md)
- [TechnicalError](opsteps/TechnicalError.md)

## Request Format
- [GetAccountBalanceRQFmt](formats/GetAccountBalanceRQFmt.md)

## Reply Format
- [GetAccountBalanceRSFmt](formats/GetAccountBalanceRSFmt.md)

## Other Formats
- csErrorReplyFormat: [StandardErrorRSFmt](formats/StandardErrorRSFmt.md)

## Java Dependencies
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)
- [com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP](classes/com/ibm/il/dse/operations/ivr/db/GetAccountBalanceSP.md)
- [com.ibm.il.dse.operations.ivr.db.LogIvrSession](classes/com/ibm/il/dse/operations/ivr/db/LogIvrSession.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
    m_ValidateRequest_5o0u49["ValidateRequest"] -->|"on0Do"| m_GetBalance_18i8gcm["GetBalance"]
    m_ValidateRequest_5o0u49["ValidateRequest"] -->|"onOtherDo"| m_ValidationFailed_8zi59y["ValidationFailed"]
    m_GetBalance_18i8gcm["GetBalance"] -->|"on0Do"| m_LogIvrCall_zne2vz["LogIvrCall"]
    m_GetBalance_18i8gcm["GetBalance"] -->|"on4Do"| m_AccountNotFound_m44om4["AccountNotFound"]
    m_GetBalance_18i8gcm["GetBalance"] -->|"on8Do"| m_DatabaseError_1pu6otp["DatabaseError"]
    m_GetBalance_18i8gcm["GetBalance"] -->|"onOtherDo"| m_TechnicalError_sy098r["TechnicalError"]
    m_LogIvrCall_zne2vz["LogIvrCall"] -->|"on0Do"| m_end_25ln["End"]
    m_LogIvrCall_zne2vz["LogIvrCall"] -->|"onOtherDo"| m_end_25ln["End"]
    m_AccountNotFound_m44om4["AccountNotFound"] -->|"onOtherDo"| m_end_25ln["End"]
    m_AccountNotFound_m44om4["AccountNotFound"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_ValidationFailed_8zi59y["ValidationFailed"] -->|"onOtherDo"| m_end_25ln["End"]
    m_ValidationFailed_8zi59y["ValidationFailed"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_DatabaseError_1pu6otp["DatabaseError"] -->|"onOtherDo"| m_end_25ln["End"]
    m_DatabaseError_1pu6otp["DatabaseError"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
    m_TechnicalError_sy098r["TechnicalError"] -->|"onOtherDo"| m_end_25ln["End"]
    m_TechnicalError_sy098r["TechnicalError"] -.->|"RC0-&gt;body"| m_ErrorBody_12kzq96["ErrorBody"]
```
