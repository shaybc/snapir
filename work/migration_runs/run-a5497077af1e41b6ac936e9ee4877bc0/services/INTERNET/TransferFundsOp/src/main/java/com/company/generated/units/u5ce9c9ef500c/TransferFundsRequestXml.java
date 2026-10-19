package com.company.generated.units.u5ce9c9ef500c;

import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;

@JacksonXmlRootElement(localName = "TransferFunds")
public class TransferFundsRequestXml {
    @JacksonXmlProperty(localName = "SourceAccount")
    public String sourceAccount;

    @JacksonXmlProperty(localName = "TargetAccount")
    public String targetAccount;

    @JacksonXmlProperty(localName = "Amount")
    public String amount;

    @JacksonXmlProperty(localName = "Currency")
    public String currency;

    @JacksonXmlProperty(localName = "SessionToken")
    public String sessionToken;

    @JacksonXmlProperty(localName = "TransferReference")
    public String transferReference;

    @JacksonXmlProperty(localName = "ScheduledDate")
    public String scheduledDate;
}