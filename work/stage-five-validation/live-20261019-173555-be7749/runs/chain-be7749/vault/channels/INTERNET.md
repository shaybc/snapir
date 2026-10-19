# Channel: INTERNET

---
entity_type: channel
entity_id: INTERNET
operation_count: 5
---

## Import Chain
- XML

## Tag Mappings
- Base64Decorator -> com.ibm.il.dse.cc.decorator.Base64Decorator
- CCBoolean -> com.ibm.il.dse.cc.format.CCBoolean
- CCConditionalString -> com.ibm.il.dse.cc.format.CCConditionalString
- CCConstant -> com.ibm.il.dse.cc.format.CCConstant
- CCDSEServerOperation -> com.ibm.il.dse.cc.cut.CCDSEServerOperation
- CCDate -> com.ibm.il.dse.cc.format.CCDate
- CCEnumFormat -> com.ibm.il.dse.cc.format.CCEnumFormat
- CCFixedLength -> com.ibm.il.dse.cc.decorator.CCFixedLength
- CCHostName -> com.ibm.il.dse.cc.format.CCHostName
- CCIColl -> com.ibm.il.dse.cc.format.CCIColl
- CCKColl -> com.ibm.il.dse.cc.format.CCKColl
- CCLength -> com.ibm.il.dse.cc.format.CCLength
- CCMandatory -> com.ibm.il.dse.cc.decorator.CCMandatory
- CCNotNull -> com.ibm.il.dse.cc.decorator.CCNotNull
- CCNullToZero -> com.ibm.il.dse.cc.decorator.CCNullToZero
- CCPadding -> com.ibm.il.dse.cc.decorator.CCPadding
- CCReflect -> com.ibm.il.dse.cc.format.CCReflect
- CCRegExp -> com.ibm.il.dse.cc.decorator.CCRegExp
- CCRegExpReplace -> com.ibm.il.dse.cc.decorator.CCRegExpReplace
- CCString -> com.ibm.il.dse.cc.format.CCString
- CCSysTimeDate -> com.ibm.il.dse.cc.format.CCSysTimeDate
- CCTableFormat -> com.ibm.il.dse.cc.format.CCTableFormat
- CCTagValue -> com.ibm.il.dse.cc.format.CCTagValue
- CCTime -> com.ibm.il.dse.cc.format.CCTime
- CCXML -> com.ibm.il.dse.cc.format.CCXML
- CCZeroToNull -> com.ibm.il.dse.cc.decorator.CCZeroToNull
- CallCorebanking -> com.ibm.il.dse.operations.internet.service.CallCorebanking
- CallFraudDetection -> com.ibm.il.dse.operations.internet.service.CallFraudDetection
- ExecuteTransferSP -> com.ibm.il.dse.operations.internet.db.ExecuteTransferSP
- GetAccountDetailsSP -> com.ibm.il.dse.operations.internet.db.GetAccountDetailsSP
- GetAccountTransactionsSP -> com.ibm.il.dse.operations.internet.db.GetAccountTransactionsSP
- GetClientAccountsSP -> com.ibm.il.dse.operations.internet.db.GetClientAccountsSP
- GetClientLinksSP -> com.ibm.il.dse.operations.internet.db.GetClientLinksSP
- MapErrorByValueAlways -> com.ibm.il.dse.operations.common.MapErrorByValueAlways
- MapErrorConditional -> com.ibm.il.dse.operations.common.MapErrorConditional
- MaskLogDecorator -> com.ibm.il.dse.cc.decorator.MaskLogDecorator
- NumberFormat -> com.ibm.il.dse.cc.format.NumberFormat
- RemoveLeadingZerosDecorator -> com.ibm.il.dse.cc.decorator.RemoveLeadingZerosDecorator
- SetCenturyFor2DigitsYear -> com.ibm.il.dse.cc.decorator.SetCenturyFor2DigitsYear
- SetChannelContext -> com.ibm.il.dse.operations.common.SetChannelContext
- ValidateInputFields -> com.ibm.il.dse.operations.common.ValidateInputFields
- ValidateTransferLimitsSP -> com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP
- nilDecorator -> com.ibm.il.dse.cc.decorator.NilDecorator

## Operations (5)
- GetAccountDetailsOp -- `Xml Definition/Channel/INTERNET/selfDefOper/GetAccountDetails.xml`
- GetClientLinksOp -- `Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml`
- GetClientOverviewOp -- `Xml Definition/Channel/INTERNET/selfDefOper/GetClientOverview.xml`
- TransferFundsOp -- `Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml`
- ValidateClientLinksOp -- `Xml Definition/Channel/INTERNET/selfDefOper/ValidateClientLinks.xml`
