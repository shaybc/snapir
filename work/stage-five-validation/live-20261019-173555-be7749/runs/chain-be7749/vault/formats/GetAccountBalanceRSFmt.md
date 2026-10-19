# GetAccountBalanceRSFmt

---
entity_type: format
entity_id: GetAccountBalanceRSFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetAccountBalanceOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetAccountBalance.xml
source_hash: 0fb403fd7c6dea2ff8390f4079959769b0e3c15a2c3538965bbb50b481dd4c2e
---

## Structure
```xml
<CCXML dataName="GetAccountBalanceResponse">
  <CCString dataName="AccountNumber">
  </CCString>
    decorator: <CCPadding length="10" padChar="0"/>
  <NumberFormat dataName="AvailableBalance" showDecimalsSep="yes" showThousandsSep="no"/>
  <NumberFormat dataName="BookBalance" showDecimalsSep="yes" showThousandsSep="no"/>
  <CCString dataName="Currency">
  </CCString>
    decorator: <CCPadding length="3" padChar=" "/>
  <CCDate dataName="BalanceDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no"/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCPadding](formats/CCPadding.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCDate](formats/CCDate.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)

## Inferred External Dependencies
- None
