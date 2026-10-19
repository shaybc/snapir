package com.company.generated.units.u561a01497abb;

import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;

@JacksonXmlRootElement(localName = "GetClientLinks")
public class GetClientLinksRequestXml {
    @JacksonXmlProperty(localName = "ClientId")
    public String clientId;

    @JacksonXmlProperty(localName = "BankId")
    public String bankId;
}
