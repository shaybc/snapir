package com.company.generated.units.u66bf2c108225;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import org.w3c.dom.Element;

public class StandardErrorRSFmtAdapterTest {
    private final StandardErrorRSFmtMapper mapper = new StandardErrorRSFmtMapper();
    private static final String XSI = "http://www.w3.org/2001/XMLSchema-instance";

    private Element parseXml(String xml) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8))).getDocumentElement();
    }

    @Test
    public void verifiesXmlStructureAndNamespaces() throws Exception {
        StandardErrorRSFmtMapper.ErrorReply reply = new StandardErrorRSFmtMapper.ErrorReply("CAT", "999", "Desc", null);
        String xml = mapper.format(reply);
        Element root = parseXml(xml);

        assertEquals("ErrorReply", root.getTagName());
        assertFalse(xml.startsWith("<?xml"));

        Element reqIdElem = (Element) root.getElementsByTagName("RequestId").item(0);
        assertNotNull(reqIdElem);
        assertEquals("true", reqIdElem.getAttributeNS(XSI, "nil"));
    }
}
