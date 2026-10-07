# GetAccountDetailsRSFmt

---
entity_type: format
entity_id: GetAccountDetailsRSFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetAccountDetailsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetAccountDetails.xml
source_hash: 3b0a5c48426c37795e96fa132e1ae902d2a7f7181f2e3d60a7754a1b644d83f7
---

## Structure
```xml
<CCXML dataName="GetAccountDetailsResponse">
  <CCString dataName="AccountNumber">
  </CCString>
    decorator: <CCPadding length="10" padChar="0"/>
  <CCString dataName="AccountHolderName"/>
  <CCTableFormat dataName="AccountTypeName" fromColumn="TYPE_DESC" fromTable="ACCOUNT_TYPES" keyValue="AccountTypeCode"/>
  <CCString dataName="AccountTypeCode"/>
  <CCString dataName="BranchCode">
  </CCString>
    decorator: <CCPadding length="3" padChar="0"/>
  <CCString dataName="BranchName">
  </CCString>
    decorator: <nilDecorator/>
  <CCDate dataName="OpenDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no"/>
  <CCDate dataName="LastActivityDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no">
  </CCDate>
    decorator: <nilDecorator/>
  <CCKColl dataName="Balances">
    <NumberFormat dataName="AvailableBalance" showDecimalsSep="yes" showThousandsSep="no"/>
    <NumberFormat dataName="BookBalance" showDecimalsSep="yes" showThousandsSep="no"/>
    <NumberFormat dataName="HoldAmount" showDecimalsSep="yes" showThousandsSep="no">
    </NumberFormat>
      decorator: <nilDecorator/>
    <CCString dataName="Currency">
    </CCString>
      decorator: <CCPadding length="3" padChar=" "/>
  </CCKColl>
  <CCIColl dataName="Transactions" times="*">
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
  </CCIColl>
  <CCString dataName="TransactionCount">
  </CCString>
    decorator: <RemoveLeadingZerosDecorator/>
</CCXML>
```

## Database Lookups
> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.

- CCTableFormat: fromTable `ACCOUNT_TYPES`, fromColumn `TYPE_DESC`, keyValue `AccountTypeCode`
- CCTableFormat: fromTable `TRANSACTION_TYPES`, fromColumn `TYPE_DESC`, keyValue `TransactionTypeCode`


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCPadding](formats/CCPadding.md)
- [CCTableFormat](formats/CCTableFormat.md)
- [nilDecorator](formats/nilDecorator.md)
- [CCDate](formats/CCDate.md)
- [CCKColl](formats/CCKColl.md)
- [NumberFormat](formats/NumberFormat.md)
- [CCIColl](formats/CCIColl.md)
- [CCTime](formats/CCTime.md)
- [RemoveLeadingZerosDecorator](formats/RemoveLeadingZerosDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)
- [com.ibm.il.dse.cc.format.CCKColl](classes/com/ibm/il/dse/cc/format/CCKColl.md)
- [com.ibm.il.dse.cc.format.NumberFormat](classes/com/ibm/il/dse/cc/format/NumberFormat.md)
- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)
- com.ibm.il.dse.cc.format.CCTime
- [com.ibm.il.dse.cc.decorator.RemoveLeadingZerosDecorator](classes/com/ibm/il/dse/cc/decorator/RemoveLeadingZerosDecorator.md)

## Inferred External Dependencies
- Database
