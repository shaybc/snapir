# AccountSummaryFmt

---
entity_type: format
entity_id: AccountSummaryFmt
conversion_status: not_started
shared: false
used_by_operations: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\defaultFile\dseformat.xml
source_hash: d7f422f36bb086464fe11e6974af0d2817462ce519006e86c4f8fd221c30b65d
---

## Structure
```xml
<CCXML dataName="Account">
  <CCString dataName="AccountNumber">
  </CCString>
    decorator: <CCPadding length="10" padChar="0"/>
  <CCTableFormat dataName="AccountTypeName" fromColumn="TYPE_DESC" fromTable="ACCOUNT_TYPES" keyValue="AccountTypeCode">
  </CCTableFormat>
    decorator: <nilDecorator/>
  <CCString dataName="AccountTypeCode"/>
  <CCString dataName="AccountNickname">
  </CCString>
    decorator: <nilDecorator/>
  <NumberFormat dataName="AvailableBalance" showDecimalsSep="yes" showThousandsSep="no"/>
  <CCString dataName="Currency">
  </CCString>
    decorator: <CCPadding length="3" padChar=" "/>
  <CCBoolean dataName="IsActive"/>
  <CCDate dataName="OpenDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no"/>
</CCXML>
```

## Database Lookups
> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.

- CCTableFormat: fromTable `ACCOUNT_TYPES`, fromColumn `TYPE_DESC`, keyValue `AccountTypeCode`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCPadding](formats/CCPadding.md)
- [CCTableFormat](formats/CCTableFormat.md)
- [nilDecorator](formats/nilDecorator.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCBoolean](formats/CCBoolean.md)
- [CCDate](formats/CCDate.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)

## Inferred External Dependencies
- Database
