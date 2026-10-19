# TransferFundsRQFmt

---
entity_type: format
entity_id: TransferFundsRQFmt
conversion_status: not_started
shared: false
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Structure
```xml
<CCXML dataName="TransferFunds">
  <CCString dataName="SourceAccount">
  </CCString>
    decorator: <CCMandatory/>
    decorator: <CCPadding length="10" padChar="0"/>
  <CCString dataName="TargetAccount">
  </CCString>
    decorator: <CCMandatory/>
    decorator: <CCPadding length="10" padChar="0"/>
  <NumberFormat dataName="Amount" showDecimalsSep="yes" showThousandsSep="no">
  </NumberFormat>
    decorator: <CCMandatory/>
  <CCString dataName="Currency">
  </CCString>
    decorator: <CCPadding length="3" padChar=" "/>
  <CCString dataName="SessionToken">
  </CCString>
    decorator: <CCMandatory/>
    decorator: <MaskLogDecorator/>
  <CCString dataName="TransferReference">
  </CCString>
    decorator: <nilDecorator/>
  <CCString dataName="ScheduledDate">
  </CCString>
    decorator: <nilDecorator/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCMandatory](formats/CCMandatory.md)
- [CCPadding](formats/CCPadding.md)
- [NumberFormat](formats/NumberFormat.md)
- [MaskLogDecorator](formats/MaskLogDecorator.md)
- [nilDecorator](formats/nilDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.decorator.MaskLogDecorator](classes/com/ibm/il/dse/cc/decorator/MaskLogDecorator.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)

## Inferred External Dependencies
- None
