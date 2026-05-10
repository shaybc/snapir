# ListLoansRSFmt

---
entity_type: format
entity_id: ListLoansRSFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="ListLoansResponse">
  <CCTcoll append="true" dataName="Loans" times="*" transparentSource="true">
    <CCXML dataName="Loan">
      <CCString dataName="LoanId"/>
      <CCString dataName="LoanType"/>
      <NumberFormat dataName="OutstandingBalance" showDecimalsSep="yes" showThousandsSep="no"/>
      <NumberFormat dataName="MonthlyPayment" showDecimalsSep="yes" showThousandsSep="no"/>
      <CCDate dataName="NextPaymentDate" fourDigYear="yes" onFailed="current" ordering="ymd" pattern="yyyyMMdd" usePattern="yes" useSep="no"/>
    </CCXML>
  </CCTcoll>
</CCXML>
```

## Used By Operations
- [ListLoansOp](operations/ListLoansOp.md)

## Referenced XML Tags
- CCXML
- CCTcoll
- CCString
- NumberFormat
- CCDate

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCTcoll](classes/demo/bankcomposer/formats/CCTcoll.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)
- [demo.bankcomposer.formats.NumberFormat](classes/demo/bankcomposer/formats/NumberFormat.md)
- [demo.bankcomposer.formats.CCDate](classes/demo/bankcomposer/formats/CCDate.md)

## Inferred External Dependencies
- None
