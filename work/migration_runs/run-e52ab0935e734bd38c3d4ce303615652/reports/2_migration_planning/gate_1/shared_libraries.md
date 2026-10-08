# Shared-library decisions

[Gate One overview](../gate_1_report.md)


## PROPOSED COMPONENT OWNERSHIP
Other legacy consumers show where the same components are used across the workspace.  
Current assignment rules: shared library at 5 or more distinct operation consumers; common library above 10.  
Each channel-and-operation pair counts once toward sharing thresholds.  
Library build order: Shared library 1 (shared-33e19da28f26) -> Shared library 2 (shared-aacf434ff625)  
Shared library 1 (shared-33e19da28f26) depends on: No other proposed libraries  
Shared library 2 (shared-aacf434ff625) depends on: Shared library 1 (shared-33e19da28f26)  

<details>
<summary>format: TransferFundsRSFmt — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>format: StandardErrorRSFmt — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>context: InternetBaseCtxt — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsecontext.xml</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 4</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp</li>
</ul>
</details>


<details>
<summary>context: AccountOpCtxt — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsecontext.xml</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 3</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>context: BaseOpCtxt — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dsecontext.xml</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>format: TransferFundsRQFmt — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>context: TransferFundsCtxt — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/com/ibm/il/dse/operations/internet/db/ValidateTransferLimitsSP.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.service.communication.http.HTTPService — Operation-local code</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/service/communication/http/HTTPService.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>com.ibm.dse.base.Tag — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/dse/base/Tag.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.operations.common.MapErrorByValueAlways — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/com/ibm/il/dse/operations/common/MapErrorByValueAlways.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.format.CCXML — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/format/CCXML.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.format.CCDate — Operation-local code</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/format/CCDate.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 4</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, IVR/GetAccountBalanceOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.format.CCTime — Operation-local code</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/format/CCTime.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 2</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.operations.common.ValidateInputFields — shared-aacf434ff625</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/com/ibm/il/dse/operations/common/ValidateInputFields.java</li>
<li>Proposed destination: Shared library 2 (shared-aacf434ff625)</li>
<li>Distinct operation consumers: 5</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.format.CCBoolean — Operation-local code</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/format/CCBoolean.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 3</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.decorator.NilDecorator — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/decorator/NilDecorator.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.operations.internet.service.CallFraudDetection — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/com/ibm/il/dse/operations/internet/service/CallFraudDetection.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>com.ibm.dse.base.Context — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/dse/base/Context.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.format.NumberFormat — shared-aacf434ff625</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/format/NumberFormat.java</li>
<li>Proposed destination: Shared library 2 (shared-aacf434ff625)</li>
<li>Distinct operation consumers: 5</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.decorator.CCPadding — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/decorator/CCPadding.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.cut.CCDSEServerOperation — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/cut/CCDSEServerOperation.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.dse.base.CCOperationStep — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/dse/base/CCOperationStep.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.format.CCString — shared-33e19da28f26</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/format/CCString.java</li>
<li>Proposed destination: Shared library 1 (shared-33e19da28f26)</li>
<li>Distinct operation consumers: 6</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): INTERNET/GetAccountDetailsOp, INTERNET/GetClientAccountsOp, INTERNET/GetClientLinksOp, IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.operations.internet.db.ExecuteTransferSP — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/com/ibm/il/dse/operations/internet/db/ExecuteTransferSP.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.operations.common.SetChannelContext — Operation-local code</summary>
<ul>
<li>Source: WSBCC_INTERNET/src/com/ibm/il/dse/operations/common/SetChannelContext.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 1</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): None</li>
</ul>
</details>


<details>
<summary>com.ibm.il.dse.cc.decorator.MaskLogDecorator — Operation-local code</summary>
<ul>
<li>Source: WSBCC_XML/src/com/ibm/il/dse/cc/decorator/MaskLogDecorator.java</li>
<li>Proposed destination: Operation-local code</li>
<li>Distinct operation consumers: 3</li>
<li>Selected consumers: INTERNET/TransferFundsOp</li>
<li>Other legacy consumers (outside this migration): IVR/GetAccountBalanceOp, IVR/GetClientAccountsOp</li>
</ul>
</details>


## DEPENDENCY LIMITS
Static source references; dynamic/reflection and compiler-level symbol attribution remain outside this inventory  
Library diagnostics: None reported  

## HOW TO RECORD YOUR DECISION
If the proposal matches your intent, choose Approve a gate for this run, then Resume a migration.  
If the proposal needs changes or more evidence, choose Reject a gate, then address the review findings before continuing.  
Record your decision through the menu. The application binds it to this report's content.  
Machine identifiers and full library data remain in shared_library_plan.json and the run database.  
