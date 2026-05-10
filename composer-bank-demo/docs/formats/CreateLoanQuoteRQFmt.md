# CreateLoanQuoteRQFmt

---
entity_type: format
entity_id: CreateLoanQuoteRQFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="CreateLoanQuoteRequest">
  <CCString dataName="CustomerId"/>
  <NumberFormat dataName="RequestedAmount" showDecimalsSep="yes" showThousandsSep="no"/>
  <NumberFormat dataName="TermMonths" showDecimalsSep="no" showThousandsSep="no"/>
  <CCString dataName="Purpose"/>
</CCXML>
```

## Used By Operations
- [CreateLoanQuoteOp](operations/CreateLoanQuoteOp.md)

## Referenced XML Tags
- CCXML
- CCString
- NumberFormat

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)
- [demo.bankcomposer.formats.NumberFormat](classes/demo/bankcomposer/formats/NumberFormat.md)

## Inferred External Dependencies
- None
