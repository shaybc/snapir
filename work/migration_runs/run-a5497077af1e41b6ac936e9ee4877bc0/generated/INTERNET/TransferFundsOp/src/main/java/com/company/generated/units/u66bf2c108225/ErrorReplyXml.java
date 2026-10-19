package com.company.generated.units.u66bf2c108225;

import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;

@JacksonXmlRootElement(localName = "ErrorReply")
public class ErrorReplyXml {
    @JacksonXmlProperty(localName = "ErrorCategory")
    public String errorCategory;

    @JacksonXmlProperty(localName = "ErrorNumber")
    public String errorNumber;

    @JacksonXmlProperty(localName = "ErrorDescription")
    public String errorDescription;

    @JacksonXmlProperty(localName = "RequestId")
    public String requestId;

    @JacksonXmlProperty(localName = "xsi:nil", isAttribute = true)
    public String xsiNil;
}
