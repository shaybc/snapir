# INTERNET / GetClientLinksOp

[Gate One overview](../../gate_1_report.md) · [Shared-library decisions](../shared_libraries.md)

## GATE ONE: REVIEW THE PROPOSED MIGRATION PLAN

Decision: Do you approve the operations, batch order and component ownership proposed below?  
Approval accepts this plan as the basis for conversion.  

## MIGRATION SCOPE
Selected channels: INTERNET  
Requested operations: GetClientLinksOp  
Excluded operations: None  
Proposed operations: 1  
Proposed batches: 1  

Batch 1 (pilot: the first conversion batch)  
- INTERNET / GetClientLinksOp; target: java  
  Planner classification: db bound  
  Meaning: The operation depends on database or stored-procedure work that must be preserved.  
  Recorded evidence: 4 steps; 4 distinct transition labels across those steps.  
  Transition labels identify the results that determine the next step.  
  References to formats shared with other operations: 3.  
  Planner assessment: Prerequisite base operation in wave 1  

Batch composition: distinct dependencies recorded for the selected operations  
Totals count each definition or Java class once across this batch.  

Component type | Count
---------------|------
Operation step definitions | 4
Format definitions | 3
Context definitions | 3
Formatter definitions | 17
Decorator definitions | 6
Java implementation classes | 10
Additional Java dependencies | 3

Additional Java dependencies are identified by static source analysis; inspect source for dynamic dependencies.  

Components used by INTERNET / GetClientLinksOp  

<details>
<summary>Operation step definitions: 4</summary>
<ul>
<li>DatabaseError (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/CCDSEServerOperation[1]/opStep[3])</li>
<li>GetClientLinks (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/CCDSEServerOperation[1]/opStep[1])</li>
<li>NoLinksFound (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/CCDSEServerOperation[1]/opStep[2])</li>
<li>TechnicalError (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/CCDSEServerOperation[1]/opStep[4])</li>
</ul>
</details>


<details>
<summary>Format definitions: 3</summary>
<ul>
<li>GetClientLinksRQFmt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[1])</li>
<li>GetClientLinksRSFmt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2])</li>
<li>StandardErrorRSFmt (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3])</li>
</ul>
</details>


<details>
<summary>Context definitions: 3</summary>
<ul>
<li>BaseOpCtxt (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dsecontext.xml; /XML[1]/context[1])</li>
<li>GetClientLinksCtxt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/context[1])</li>
<li>InternetBaseCtxt (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsecontext.xml; /XML[1]/context[1])</li>
</ul>
</details>


<details>
<summary>Formatter definitions: 17</summary>
<ul>
<li>CCBoolean (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCBoolean[1])</li>
<li>CCIColl (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCString[2])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCString[2])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCString[3])</li>
<li>CCString (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[1])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[2])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[3])</li>
<li>CCString (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/CCString[4])</li>
<li>CCTableFormat (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCTableFormat[1])</li>
<li>CCXML (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[1]/CCXML[1])</li>
<li>CCXML (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1])</li>
<li>CCXML (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1])</li>
<li>CCXML (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1])</li>
</ul>
</details>


<details>
<summary>Decorator definitions: 6</summary>
<ul>
<li>CCMandatory (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1])</li>
<li>CCMandatory (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCMandatory[1])</li>
<li>CCPadding (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1])</li>
<li>nilDecorator (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/nilDecorator[1])</li>
<li>nilDecorator (WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml; /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/nilDecorator[2])</li>
<li>nilDecorator (WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml; /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1])</li>
</ul>
</details>


<details>
<summary>Java implementation classes: 10</summary>
<ul>
<li>com.ibm.il.dse.cc.cut.CCDSEServerOperation</li>
<li>com.ibm.il.dse.cc.decorator.CCPadding</li>
<li>com.ibm.il.dse.cc.decorator.NilDecorator</li>
<li>com.ibm.il.dse.cc.format.CCBoolean</li>
<li>com.ibm.il.dse.cc.format.CCIColl</li>
<li>com.ibm.il.dse.cc.format.CCString</li>
<li>com.ibm.il.dse.cc.format.CCTableFormat</li>
<li>com.ibm.il.dse.cc.format.CCXML</li>
<li>com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>com.ibm.il.dse.operations.internet.db.GetClientLinksSP</li>
</ul>
</details>


<details>
<summary>Additional Java dependencies: 3</summary>
<ul>
<li>com.ibm.dse.base.CCOperationStep</li>
<li>com.ibm.dse.base.Context</li>
<li>com.ibm.dse.base.Tag</li>
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

INTERNET/GetClientLinksOp  

<details>
<summary>Step: GetClientLinks</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.internet.db.GetClientLinksSP</li>
<li>Return code 0 -&gt; Finish the operation</li>
<li>Return code 4 -&gt; Go to step NoLinksFound</li>
<li>Return code 8 -&gt; Go to step DatabaseError</li>
<li>Any other result -&gt; Go to step TechnicalError</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientLinks.xml</li>
</ul>
</details>


<details>
<summary>Step: NoLinksFound</summary>
<ul>
<li>Implementation: com.ibm.il.dse.operations.common.MapErrorByValueAlways</li>
<li>Any other result -&gt; Finish the operation</li>
<li>Source: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientLinks.xml</li>
</ul>
</details>
