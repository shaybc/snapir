# TransferFundsRSFmt

---
entity_type: format
entity_id: TransferFundsRSFmt
conversion_status: not_started
shared: false
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Structure
```xml
<CCXML dataName="TransferFundsResponse">
  <CCString dataName="TransferId"/>
  <CCString dataName="TransferStatus"/>
  <CCDate dataName="ExecutionDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no"/>
  <CCTime dataName="ExecutionTime"/>
  <NumberFormat dataName="Amount" showDecimalsSep="yes" showThousandsSep="no"/>
  <CCString dataName="Currency">
  </CCString>
    decorator: <CCPadding length="3" padChar=" "/>
  <CCString dataName="SourceAccount">
  </CCString>
    decorator: <CCPadding length="10" padChar="0"/>
  <CCString dataName="TargetAccount">
  </CCString>
    decorator: <CCPadding length="10" padChar="0"/>
  <NumberFormat dataName="NewSourceBalance" showDecimalsSep="yes" showThousandsSep="no">
  </NumberFormat>
    decorator: <nilDecorator/>
  <CCBoolean dataName="FraudCheckSkipped"/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCDate](formats/CCDate.md)
- [CCTime](formats/CCTime.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCPadding](formats/CCPadding.md)
- [nilDecorator](formats/nilDecorator.md)
- [CCBoolean](formats/CCBoolean.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)
- [com.ibm.il.dse.cc.format.CCTime](classes/com/ibm/il/dse/cc/format/CCTime.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)

## Inferred External Dependencies
- None
