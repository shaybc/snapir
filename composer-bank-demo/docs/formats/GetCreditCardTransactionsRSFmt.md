# GetCreditCardTransactionsRSFmt

---
entity_type: format
entity_id: GetCreditCardTransactionsRSFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="GetCreditCardTransactionsResponse">
  <CCTcoll append="true" dataName="CardTransactions" times="*" transparentSource="true">
    <CCXML dataName="CardTransaction">
      <CCString dataName="TransactionId"/>
      <CCDate dataName="TransactionDate" fourDigYear="yes" onFailed="current" ordering="ymd" pattern="yyyyMMdd" usePattern="yes" useSep="no"/>
      <CCString dataName="MerchantName"/>
      <NumberFormat dataName="Amount" showDecimalsSep="yes" showThousandsSep="no"/>
      <CCString dataName="Currency"/>
    </CCXML>
  </CCTcoll>
</CCXML>
```

## Used By Operations
- [GetCreditCardTransactionsOp](operations/GetCreditCardTransactionsOp.md)

## Referenced XML Tags
- CCXML
- CCTcoll
- CCString
- CCDate
- NumberFormat

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCTcoll](classes/demo/bankcomposer/formats/CCTcoll.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)
- [demo.bankcomposer.formats.CCDate](classes/demo/bankcomposer/formats/CCDate.md)
- [demo.bankcomposer.formats.NumberFormat](classes/demo/bankcomposer/formats/NumberFormat.md)

## Inferred External Dependencies
- None
