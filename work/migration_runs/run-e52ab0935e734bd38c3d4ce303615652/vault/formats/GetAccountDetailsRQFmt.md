# GetAccountDetailsRQFmt

---
entity_type: format
entity_id: GetAccountDetailsRQFmt
conversion_status: not_started
shared: false
used_by_operations:
  - GetAccountDetailsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetAccountDetails.xml
source_hash: 3b0a5c48426c37795e96fa132e1ae902d2a7f7181f2e3d60a7754a1b644d83f7
---

## Structure
```xml
<CCXML dataName="GetAccountDetails">
  <CCString dataName="ClientId">
  </CCString>
    decorator: <CCMandatory/>
  <CCString dataName="AccountNumber">
  </CCString>
    decorator: <CCMandatory/>
    decorator: <CCPadding length="10" padChar="0"/>
  <CCString dataName="SessionToken">
  </CCString>
    decorator: <CCMandatory/>
  <CCDate dataName="FromDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no">
  </CCDate>
    decorator: <nilDecorator/>
  <CCDate dataName="ToDate" fourDigYear="yes" pattern="yyyyMMdd" useSep="no">
  </CCDate>
    decorator: <nilDecorator/>
  <CCString dataName="MaxTransactions">
  </CCString>
    decorator: <CCNullToZero/>
    decorator: <RemoveLeadingZerosDecorator/>
</CCXML>
```


## Referenced Tags
- [CCXML](formats/CCXML.md)
- [CCString](formats/CCString.md)
- [CCMandatory](formats/CCMandatory.md)
- [CCPadding](formats/CCPadding.md)
- [CCDate](formats/CCDate.md)
- [nilDecorator](formats/nilDecorator.md)
- [CCNullToZero](formats/CCNullToZero.md)
- [RemoveLeadingZerosDecorator](formats/RemoveLeadingZerosDecorator.md)

## Mapped Java Classes
- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)
- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)
- com.ibm.il.dse.cc.decorator.CCMandatory
- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)
- [com.ibm.il.dse.cc.format.CCDate](classes/com/ibm/il/dse/cc/format/CCDate.md)
- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)
- com.ibm.il.dse.cc.decorator.CCNullToZero
- [com.ibm.il.dse.cc.decorator.RemoveLeadingZerosDecorator](classes/com/ibm/il/dse/cc/decorator/RemoveLeadingZerosDecorator.md)

## Inferred External Dependencies
- None
