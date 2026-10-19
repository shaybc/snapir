# Channel: IVR

---
entity_type: channel
entity_id: IVR
operation_count: 2
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
- GetAccountBalanceSP -> com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP
- GetClientAccountsIvrSP -> com.ibm.il.dse.operations.ivr.db.GetClientAccountsIvrSP
- LogIvrSession -> com.ibm.il.dse.operations.ivr.db.LogIvrSession
- MapErrorByValueAlways -> com.ibm.il.dse.operations.common.MapErrorByValueAlways
- MapErrorConditional -> com.ibm.il.dse.operations.common.MapErrorConditional
- MaskLogDecorator -> com.ibm.il.dse.cc.decorator.MaskLogDecorator
- NumberFormat -> com.ibm.il.dse.cc.format.NumberFormat
- RemoveLeadingZerosDecorator -> com.ibm.il.dse.cc.decorator.RemoveLeadingZerosDecorator
- SetCenturyFor2DigitsYear -> com.ibm.il.dse.cc.decorator.SetCenturyFor2DigitsYear
- SetChannelContext -> com.ibm.il.dse.operations.common.SetChannelContext
- ValidateInputFields -> com.ibm.il.dse.operations.common.ValidateInputFields
- nilDecorator -> com.ibm.il.dse.cc.decorator.NilDecorator

## Operations (2)
- GetAccountBalanceOp -- `Xml Definition/Channel/IVR/selfDefOper/GetAccountBalance.xml`
- GetClientAccountsOp -- `Xml Definition/Channel/IVR/selfDefOper/GetClientAccounts.xml`
