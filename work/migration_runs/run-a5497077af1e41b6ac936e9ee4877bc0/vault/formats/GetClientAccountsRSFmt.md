# GetClientAccountsRSFmt

---
entity_type: format
entity_id: GetClientAccountsRSFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientAccounts.xml
source_hash: c6d10b4ed4d931e4e2933f6afeb7d68804cec3db9f1e488ea24a74b332d31bb8
---

## Structure
```xml
<CCXML dataName="GetClientAccountsResponse">
  <CCString dataName="ClientId"/>
  <CCString dataName="ClientFullName">
  </CCString>
    decorator: <nilDecorator/>
  <CCIColl dataName="Accounts" times="*">
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
  </CCIColl>
  <CCString dataName="TotalAccountCount">
  </CCString>
    decorator: <RemoveLeadingZerosDecorator/>
</CCXML>
```

## Database Lookups
> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.

- CCTableFormat: fromTable `ACCOUNT_TYPES`, fromColumn `TYPE_DESC`, keyValue `AccountTypeCode`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [nilDecorator](formats/nilDecorator.md)
- [CCIColl](formats/CCIColl.md)
- [CCPadding](formats/CCPadding.md)
- [CCTableFormat](formats/CCTableFormat.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCBoolean](formats/CCBoolean.md)
- [CCDate](formats/CCDate.md)
- [RemoveLeadingZerosDecorator](formats/RemoveLeadingZerosDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)
- [com.ibm.il.dse.cc.decorator.RemoveLeadingZerosDecorator](classes/com/ibm/il/dse/cc/decorator/RemoveLeadingZerosDecorator.md)

## Inferred External Dependencies
- Database
