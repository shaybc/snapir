package com.company.generated.units.u66bf2c108225;

import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator;

public class StandardErrorRSFmtMapper {

    private final XmlMapper xmlMapper;

    public StandardErrorRSFmtMapper() {
        this.xmlMapper = new XmlMapper();
        this.xmlMapper.disable(SerializationFeature.WRITE_EMPTY_JSON_ARRAYS);
        this.xmlMapper.configure(ToXmlGenerator.Feature.WRITE_XML_DECLARATION, false);
    }

    public String format(ErrorReply reply) throws Exception {
        if (reply == null) {
            return "<ErrorReply xsi:nil=\"true\"/>";
        }
        ErrorReplyXml wire = new ErrorReplyXml();
        wire.errorCategory = reply.getErrorCategory();
        wire.errorNumber = reply.getErrorNumber();
        wire.errorDescription = reply.getErrorDescription();
        wire.requestId = reply.getRequestId();

        if (isNil(wire.errorCategory) && isNil(wire.errorNumber) && isNil(wire.errorDescription) && isNil(wire.requestId)) {
            wire.xsiNil = "true";
        }

        return xmlMapper.writeValueAsString(wire);
    }

    public ErrorReply unformat(String xml) throws Exception {
        if (xml == null || xml.isBlank() || xml.contains("xsi:nil=\"true\"")) {
            return null;
        }
        ErrorReplyXml wire = xmlMapper.readValue(xml, ErrorReplyXml.class);
        if (wire == null) {
            return null;
        }
        return new ErrorReply(wire.errorCategory, wire.errorNumber, wire.errorDescription, wire.requestId);
    }

    private boolean isNil(String val) {
        return val == null || val.isBlank();
    }
}
