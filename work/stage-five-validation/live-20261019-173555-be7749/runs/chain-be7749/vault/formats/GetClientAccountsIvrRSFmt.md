# GetClientAccountsIvrRSFmt

---
entity_type: format
entity_id: GetClientAccountsIvrRSFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetClientAccounts.xml
source_hash: 9dcc938f33cbdec98354dbeb023d9574ed8f2df9476a13e128ee8f7b171d76dc
---

## Structure
```xml
<CCXML dataName="GetClientAccountsResponse">
  <CCIColl dataName="Accounts" times="*">
    <CCXML dataName="Account">
      <CCString dataName="AccountNumber">
      </CCString>
        decorator: <CCPadding length="10" padChar="0"/>
      <CCString dataName="AccountTypeCode"/>
      <NumberFormat dataName="AvailableBalance" showDecimalsSep="yes" showThousandsSep="no"/>
      <CCString dataName="Currency">
      </CCString>
        decorator: <CCPadding length="3" padChar=" "/>
    </CCXML>
  </CCIColl>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCIColl](formats/CCIColl.md)
- [CCString](formats/CCString.md)
- [CCPadding](formats/CCPadding.md)
- [NumberFormat](formats/NumberFormat.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)

## Inferred External Dependencies
- None
