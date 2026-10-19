package com.company.generated.units.u66bf2c108225;

import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator;
import java.util.Objects;

public final class StandardErrorRSFmtMapper {
    private final XmlMapper xmlMapper;
    private static final String XSI_NS = "http://www.w3.org/2001/XMLSchema-instance";

    public StandardErrorRSFmtMapper() {
        this.xmlMapper = new XmlMapper();
        this.xmlMapper.configure(ToXmlGenerator.Feature.WRITE_XML_DECLARATION, false);
    }

    @JacksonXmlRootElement(localName = "ErrorReply")
    public static class ErrorReplyWire {
        @JacksonXmlProperty(localName = "ErrorCategory")
        public String errorCategory;

        @JacksonXmlProperty(localName = "ErrorNumber")
        public String errorNumber;

        @JacksonXmlProperty(localName = "ErrorDescription")
        public String errorDescription;

        @JacksonXmlProperty(localName = "RequestId")
        public NullableRequestId requestId;
    }

    public static class NullableRequestId {
        @JacksonXmlText
        public String value;

        @JacksonXmlProperty(localName = "nil", isAttribute = true, namespace = XSI_NS)
        public String nil;
    }

    public record ErrorReply(String errorCategory, String errorNumber, String errorDescription, String requestId) {}

    public String format(ErrorReply reply) throws Exception {
        Objects.requireNonNull(reply, "ErrorReply must not be null");
        ErrorReplyWire wire = new ErrorReplyWire();
        wire.errorCategory = reply.errorCategory();
        wire.errorNumber = reply.errorNumber();
        wire.errorDescription = reply.errorDescription();
        
        wire.requestId = new NullableRequestId();
        if (reply.requestId() == null) {
            wire.requestId.nil = "true";
        } else {
            wire.requestId.value = reply.requestId();
        }
        return xmlMapper.writeValueAsString(wire);
    }

    public ErrorReply unformat(String xml) throws Exception {
        ErrorReplyWire wire = xmlMapper.readValue(xml, ErrorReplyWire.class);
        Objects.requireNonNull(wire, "Deserialized wire structure must not be null");
        
        String reqId = null;
        if (wire.requestId != null && !"true".equals(wire.requestId.nil)) {
            reqId = wire.requestId.value;
        }
        return new ErrorReply(wire.errorCategory, wire.errorNumber, wire.errorDescription, reqId);
    }
}
