# INTERNET / TransferFundsOp

[Gate One overview](../../gate_1_report.md) · [Shared-library decisions](../shared_libraries.md)

## GATE ONE: REVIEW THE PROPOSED MIGRATION PLAN

Decision: Do you approve the operations, batch order and component ownership proposed below?  
Approval accepts this plan as the basis for conversion.  

## MIGRATION SCOPE
Selected channels: INTERNET  
Requested operations: TransferFundsOp  
Excluded operations: None  
Proposed operations: 1  
Proposed batches: 1  

Batch 1 (pilot: the first conversion batch)  
- INTERNET / TransferFundsOp; target: java  
  Planner classification: db bound  
  Meaning: The operation depends on database or stored-procedure work that must be preserved.  
  Recorded evidence: 14 steps; 10 distinct transition labels across those steps.  
  Transition labels identify the results that determine the next step.  
  References to formats shared with other operations: 1.  
  Planner assessment: Assigned to db bound due to db accessor behavior type.  
  Planner assessment: Included in pilot batch as scope size is less than three operations.  

Batch composition: distinct dependencies recorded for the selected operations  
Totals count each definition or Java class once across this batch.  

Component type | Count
---------------|------
Operation step definitions | 14
Format definitions | 3
Context definitions | 4
Formatter definitions | 24
Decorator definitions | 15
Java implementation classes | 16
Additional Java dependencies | 4

Additional Java dependencies are identified by static source analysis; inspect source for dynamic dependencies.  

Components used by INTERNET / TransferFundsOp  

<details>
<summary>Operation step definitions: 14</summary>
<ul>
<li>AccountNotEligible (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[9])</li>
<li>CheckLimits (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[2])</li>
<li>CoreBankingRejected (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[11])</li>
<li>DailyLimitExceeded (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[8])</li>
<li>DatabaseError (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[13])</li>
<li>ExecuteTransfer (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[5])</li>
<li>FraudCheck (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[3])</li>
<li>FraudSuspected (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[10])</li>
<li>InsufficientFunds (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[7])</li>
<li>SkipFraudOnTimeout (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[4])</li>
<li>TechnicalError (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[14])</li>
<li>TransferAlreadyProcessed (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[12])</li>
<li>ValidateTransfer (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[1])</li>
<li>ValidationFailed (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/CCDSEServerOperation[1]/opStep[6])</li>
</ul>
</details>


<details>
<summary>Format definitions: 3</summary>
<ul>
<li>StandardErrorRSFmt (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3])</li>
<li>TransferFundsRQFmt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1])</li>
<li>TransferFundsRSFmt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2])</li>
</ul>
</details>


<details>
<summary>Context definitions: 4</summary>
<ul>
<li>AccountOpCtxt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsecontext.xml; /XML[1]/context[2])</li>
<li>BaseOpCtxt (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dsecontext.xml; /XML[1]/context[1])</li>
<li>InternetBaseCtxt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsecontext.xml; /XML[1]/context[1])</li>
<li>TransferFundsCtxt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/context[1])</li>
</ul>
</details>


<details>
<summary>Formatter definitions: 24</summary>
<ul>
<li>CCBoolean (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCBoolean[1])</li>
<li>CCDate (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCDate[1])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[2])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[3])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[4])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[5])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[6])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCString[2])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCString[3])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCString[4])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCString[5])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[2])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[3])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[4])</li>
<li>CCTime (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCTime[1])</li>
<li>CCXML (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1])</li>
<li>CCXML (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1])</li>
<li>CCXML (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1])</li>
<li>NumberFormat (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/NumberFormat[1])</li>
<li>NumberFormat (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/NumberFormat[1])</li>
<li>NumberFormat (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/NumberFormat[2])</li>
</ul>
</details>


<details>
<summary>Decorator definitions: 15</summary>
<ul>
<li>CCMandatory (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1])</li>
<li>CCMandatory (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[2])</li>
<li>CCMandatory (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[3])</li>
<li>CCMandatory (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[4])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[2])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[3])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCPadding[1])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCPadding[2])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCPadding[3])</li>
<li>MaskLogDecorator (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1])</li>
<li>nilDecorator (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/nilDecorator[1])</li>
<li>nilDecorator (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[1]/CCXML[1]/nilDecorator[2])</li>
<li>nilDecorator (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml; /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1])</li>
<li>nilDecorator (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1])</li>
</ul>
</details>


<details>
<summary>Java implementation classes: 16</summary>
<ul>
<li>com.ibm.il.dse.cc.cut.CCDSEServerOperation</li>
<li>com.ibm.il.dse.cc.decorator.CCPadding</li>
<li>com.ibm.il.dse.cc.decorator.MaskLogDecorator</li>
<li>com.ibm.il.dse.cc.decorator.NilDecorator</li>
<li>com.ibm.il.dse.cc.format.CCBoolean</li>
<li>com.ibm.il.dse.cc.format.CCDate</li>
<li>com.ibm.il.dse.cc.format.CCString</li>
<li>com.ibm.il.dse.cc.format.CCTime</li>
<li>com.ibm.il.dse.cc.format.CCXML</li>
<li>com.ibm.il.dse.cc.format.NumberFormat</li>
<li>com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>com.ibm.il.dse.operations.common.SetChannelContext</li>
<li>com.ibm.il.dse.operations.common.ValidateInputFields</li>
<li>com.ibm.il.dse.operations.internet.db.ExecuteTransferSP</li>
<li>com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP</li>
<li>com.ibm.il.dse.operations.internet.service.CallFraudDetection</li>
</ul>
</details>


<details>
<summary>Additional Java dependencies: 4</summary>
<ul>
<li>com.ibm.dse.base.CCOperationStep</li>
<li>com.ibm.dse.base.Context</li>
<li>com.ibm.dse.base.Tag</li>
<li>com.ibm.il.dse.cc.service.communication.http.HTTPService</li>
</ul>
</details>


## BLOCKERS AND APPROVAL
Operations with blocked context dependencies: 0.  
Gate One requires a decision according to the configured approval policy.  

## WHAT TO REVIEW
1. Confirm that only the intended operations and channels are proposed.  
2. Check the recorded steps and outcomes against the legacy operation.  
3. Review which named components will be shared and which will remain operation-local.  
4. Resolve any diagnostics or missing evidence before approving.  

## RECORDED LEGACY STEPS AND OUTCOMES
The following steps and outcomes were extracted from the legacy source.  

INTERNET/TransferFundsOp  

<details>
<summary>Step: AccountNotEligible</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: CheckLimits</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP</li>
<li>Return code 0 -&gt; Go to step FraudCheck</li>
<li>Return code 3 -&gt; Go to step DailyLimitExceeded</li>
<li>Return code 4 -&gt; Go to step InsufficientFunds</li>
<li>Return code 5 -&gt; Go to step AccountNotEligible</li>
<li>Return code 8 -&gt; Go to step DatabaseError</li>
<li>Any other result -&gt; Go to step TechnicalError</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: CoreBankingRejected</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: DailyLimitExceeded</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: DatabaseError</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: ExecuteTransfer</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.internet.db.ExecuteTransferSP</li>
<li>Return code 0 -&gt; Finish the operation</li>
<li>Return code 6 -&gt; Go to step CoreBankingRejected</li>
<li>Return code 7 -&gt; Go to step TransferAlreadyProcessed</li>
<li>Return code 8 -&gt; Go to step DatabaseError</li>
<li>Any other result -&gt; Go to step TechnicalError</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: FraudCheck</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.internet.service.CallFraudDetection</li>
<li>Return code 0 -&gt; Go to step ExecuteTransfer</li>
<li>Return code 2 -&gt; Go to step FraudSuspected</li>
<li>Any other result -&gt; Go to step TechnicalError</li>
<li>Timeout -&gt; Go to step SkipFraudOnTimeout</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: FraudSuspected</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: InsufficientFunds</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: SkipFraudOnTimeout</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.SetChannelContext</li>
<li>Return code 0 -&gt; Go to step ExecuteTransfer</li>
<li>Any other result -&gt; Go to step TechnicalError</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: TechnicalError</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: TransferAlreadyProcessed</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: ValidateTransfer</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.ValidateInputFields</li>
<li>Return code 0 -&gt; Go to step CheckLimits</li>
<li>Any other result -&gt; Go to step ValidationFailed</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>


<details>
<summary>Step: ValidationFailed</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml</li>
</ul>
</details>
