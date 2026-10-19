package com.company.generated.units.ub5afca9c05e0;

import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;

@JacksonXmlRootElement(localName = "TransferFundsResponse")
public class TransferFundsResponseXml {
    @JacksonXmlProperty(localName = "TransferId")
    public String transferId;

    @JacksonXmlProperty(localName = "TransferStatus")
    public String transferStatus;

    @JacksonXmlProperty(localName = "ExecutionDate")
    public String executionDate;

    @JacksonXmlProperty(localName = "ExecutionTime")
    public String executionTime;

    @JacksonXmlProperty(localName = "Amount")
    public String amount;

    @JacksonXmlProperty(localName = "Currency")
    public String currency;

    @JacksonXmlProperty(localName = "SourceAccount")
    public String sourceAccount;

    @JacksonXmlProperty(localName = "TargetAccount")
    public String targetAccount;

    @JacksonXmlProperty(localName = "NewSourceBalance")
    public String newSourceBalance;

    @JacksonXmlProperty(localName = "FraudCheckSkipped")
    public NullableBoolean fraudCheckSkipped;

    public static class NullableBoolean {
        @JacksonXmlText
        public String value;

        @JacksonXmlProperty(localName = "nil", isAttribute = true, namespace = "http://www.w3.org/2001/XMLSchema-instance")
        public String nil;
    }
}
