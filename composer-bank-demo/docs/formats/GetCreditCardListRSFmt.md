# GetCreditCardListRSFmt

---
entity_type: format
entity_id: GetCreditCardListRSFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="GetCreditCardListResponse">
  <CCTcoll append="true" dataName="Cards" times="*" transparentSource="true">
    <CCXML dataName="Card">
      <CCString dataName="CardId"/>
      <CCString dataName="MaskedNumber"/>
      <CCString dataName="Brand"/>
      <CCString dataName="Status"/>
      <NumberFormat dataName="AvailableCredit" showDecimalsSep="yes" showThousandsSep="no"/>
    </CCXML>
  </CCTcoll>
</CCXML>
```

## Used By Operations
- [GetCreditCardListOp](operations/GetCreditCardListOp.md)

## Referenced XML Tags
- CCXML
- CCTcoll
- CCString
- NumberFormat

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCTcoll](classes/demo/bankcomposer/formats/CCTcoll.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)
- [demo.bankcomposer.formats.NumberFormat](classes/demo/bankcomposer/formats/NumberFormat.md)

## Inferred External Dependencies
- None
