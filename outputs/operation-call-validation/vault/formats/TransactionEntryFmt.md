# TransactionEntryFmt

---
entity_type: format
entity_id: TransactionEntryFmt
conversion_status: not_started
shared: false
used_by_operations: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\defaultFile\dseformat.xml
source_hash: d7f422f36bb086464fe11e6974af0d2817462ce519006e86c4f8fd221c30b65d
---

## Structure
```xml
<CCXML dataName="Transaction">
  <CCString dataName="TransactionId"/>
  <CCDate dataName="TransactionDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no"/>
  <CCTime dataName="TransactionTime">
  </CCTime>
    decorator: <nilDecorator/>
  <CCString dataName="Description">
  </CCString>
    decorator: <nilDecorator/>
  <NumberFormat dataName="Amount" showDecimalsSep="yes" showThousandsSep="no"/>
  <CCString dataName="DebitCredit">
  </CCString>
    decorator: <CCPadding length="1" padChar=" "/>
  <CCString dataName="BalanceAfter">
  </CCString>
    decorator: <nilDecorator/>
  <CCTableFormat dataName="TransactionTypeName" fromColumn="TYPE_DESC" fromTable="TRANSACTION_TYPES" keyValue="TransactionTypeCode"/>
  <CCString dataName="TransactionTypeCode"/>
</CCXML>
```

## Database Lookups
> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.

- CCTableFormat: fromTable `TRANSACTION_TYPES`, fromColumn `TYPE_DESC`, keyValue `TransactionTypeCode`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCDate](formats/CCDate.md)
- [CCTime](formats/CCTime.md)
- [nilDecorator](formats/nilDecorator.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCPadding](formats/CCPadding.md)
- [CCTableFormat](formats/CCTableFormat.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)
- [com.ibm.il.dse.cc.format.CCTime](classes/com/ibm/il/dse/cc/format/CCTime.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)

## Inferred External Dependencies
- Database
