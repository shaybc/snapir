# CreateLoanQuoteRSFmt

---
entity_type: format
entity_id: CreateLoanQuoteRSFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="CreateLoanQuoteResponse">
  <CCString dataName="QuoteId"/>
  <NumberFormat dataName="InterestRate" showDecimalsSep="yes" showThousandsSep="no"/>
  <NumberFormat dataName="EstimatedMonthlyPayment" showDecimalsSep="yes" showThousandsSep="no"/>
  <CCDate dataName="ValidUntil" fourDigYear="yes" onFailed="current" ordering="ymd" pattern="yyyyMMdd" usePattern="yes" useSep="no"/>
</CCXML>
```

## Used By Operations
- [CreateLoanQuoteOp](operations/CreateLoanQuoteOp.md)

## Referenced XML Tags
- CCXML
- CCString
- NumberFormat
- CCDate

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)
- [demo.bankcomposer.formats.NumberFormat](classes/demo/bankcomposer/formats/NumberFormat.md)
- [demo.bankcomposer.formats.CCDate](classes/demo/bankcomposer/formats/CCDate.md)

## Inferred External Dependencies
- None
