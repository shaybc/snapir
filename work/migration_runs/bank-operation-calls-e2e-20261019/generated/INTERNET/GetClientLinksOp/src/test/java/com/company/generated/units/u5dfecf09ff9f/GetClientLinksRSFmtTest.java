package com.company.generated.units.u5dfecf09ff9f;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;

public class GetClientLinksRSFmtTest {
    private final GetClientLinksRSFmtMapper mapper = new GetClientLinksRSFmtMapper();
    private static final String XSI = "http://www.w3.org/2001/XMLSchema-instance";

    private Element parseRoot(String xml) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8))).getDocumentElement();
    }

    @Test
    public void testFormatAndUnformatSuccess() throws Exception {
        GetClientLinksRSFmtMapper.LinkDto link = new GetClientLinksRSFmtMapper.LinkDto(
            "L1", "Description 1", "http://example.com", true, "ICON1"
        );
        GetClientLinksRSFmtMapper.GetClientLinksResponse response =
            new GetClientLinksRSFmtMapper.GetClientLinksResponse("CLI123", List.of(link));

        String xml = mapper.format(response);
        assertNotNull(xml);
        Element root = parseRoot(xml);
        assertEquals("GetClientLinksResponse", root.getTagName());

        GetClientLinksRSFmtMapper.GetClientLinksResponse parsed = mapper.unformat(xml);
        assertEquals("CLI123", parsed.clientId());
        assertEquals(1, parsed.links().size());
        assertEquals("L1", parsed.links().get(0).linkId());
        assertEquals("Description 1", parsed.links().get(0).linkDescription());
        assertEquals("http://example.com", parsed.links().get(0).linkUrl());
        assertTrue(parsed.links().get(0).isExternal());
        assertEquals("ICON1", parsed.links().get(0).iconCode());
    }

    @Test
    public void testMandatoryLinkIdValidation() {
        GetClientLinksRSFmtMapper.LinkDto link = new GetClientLinksRSFmtMapper.LinkDto(
            null, "Desc", "url", false, "icon"
        );
        GetClientLinksRSFmtMapper.GetClientLinksResponse response =
            new GetClientLinksRSFmtMapper.GetClientLinksResponse("CLI", List.of(link));

        assertThrows(IllegalArgumentException.class, () -> mapper.format(response));
    }

    @Test
    public void testNilDecorators() throws Exception {
        GetClientLinksRSFmtMapper.LinkDto link = new GetClientLinksRSFmtMapper.LinkDto(
            "L2", null, "url", false, null
        );
        GetClientLinksRSFmtMapper.GetClientLinksResponse response =
            new GetClientLinksRSFmtMapper.GetClientLinksResponse("CLI", List.of(link));

        String xml = mapper.format(response);
        Element root = parseRoot(xml);
        Element linkEl = (Element) root.getElementsByTagName("Link").item(0);
        Element descEl = (Element) linkEl.getElementsByTagName("LinkDescription").item(0);
        assertEquals("true", descEl.getAttributeNS(XSI, "nil"));

        GetClientLinksRSFmtMapper.GetClientLinksResponse parsed = mapper.unformat(xml);
        assertNull(parsed.links().get(0).linkDescription());
        assertNull(parsed.links().get(0).iconCode());
    }
}
