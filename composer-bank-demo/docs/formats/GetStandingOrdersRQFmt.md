# GetStandingOrdersRQFmt

---
entity_type: format
entity_id: GetStandingOrdersRQFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="GetStandingOrdersRequest">
  <CCString dataName="CustomerId"/>
  <CCString dataName="AccountId"/>
</CCXML>
```

## Used By Operations
- [GetStandingOrdersOp](operations/GetStandingOrdersOp.md)

## Referenced XML Tags
- CCXML
- CCString

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)

## Inferred External Dependencies
- None
