# GetCustomerProfileRSFmt

---
entity_type: format
entity_id: GetCustomerProfileRSFmt
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\formats\dseformat.xml
source_hash: d3c23b2350456335e87f9e7fc66178489e4fcbb97bf9b5b3304cf8decd9c66bc
---

## Structure
```xml
<CCXML dataName="GetCustomerProfileResponse">
  <CCString dataName="CustomerId"/>
  <CCString dataName="FullName"/>
  <CCString dataName="Email"/>
  <CCString dataName="MobilePhone"/>
  <CCString dataName="PreferredLanguage"/>
  <CCBoolean dataName="MarketingConsent"/>
</CCXML>
```

## Used By Operations
- [GetCustomerProfileOp](operations/GetCustomerProfileOp.md)

## Referenced XML Tags
- CCXML
- CCString
- CCBoolean

## Mapped Java Classes From Tags
- [demo.bankcomposer.formats.CCXML](classes/demo/bankcomposer/formats/CCXML.md)
- [demo.bankcomposer.formats.CCString](classes/demo/bankcomposer/formats/CCString.md)
- [demo.bankcomposer.formats.CCBoolean](classes/demo/bankcomposer/formats/CCBoolean.md)

## Inferred External Dependencies
- None
