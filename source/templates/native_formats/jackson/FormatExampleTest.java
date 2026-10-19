package example.format;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.io.ByteArrayInputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;

/** Use real Jackson/mapper objects; derive real migration expectations from its evidence. */
public class FormatExampleTest {
    private final FormatExample mapper = new FormatExample();
    private static final String XSI = "http://www.w3.org/2001/XMLSchema-instance";

    private FormatExample.Value value(String code, Boolean enabled) {
        return new FormatExample.Value(code, new BigDecimal("12.50"), LocalDate.of(2024, 1, 2), enabled);
    }

    private Element root(String xml) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8))).getDocumentElement();
    }

    private String text(Element root, String name) {
        return root.getElementsByTagName(name).item(0).getTextContent();
    }

    @Test public void serializationPreservesStructureAndAppliesConfirmedConversions() throws Exception {
        String xml = mapper.format(value("A", false));
        Element root = root(xml);
        assertEquals("Envelope", root.getTagName());
        assertFalse(xml.startsWith("<?xml"));
        assertFalse(root.hasAttributeNS(XSI, "nil"));
        assertEquals("  A", text(root, "Code"));
        assertEquals("1250", text(root, "Amount"));
        assertEquals("20240102", text(root, "Date"));
        assertEquals("false", text(root, "Enabled"));
    }

    @Test public void paddingUsesTargetLengthRatherThanAlwaysAddingCharacters() throws Exception {
        assertEquals("ABC", text(root(mapper.format(value("ABC", true))), "Code"));
        assertEquals("ABCD", text(root(mapper.format(value("ABCD", true))), "Code"));
    }

    @Test public void parsingHasIndependentEvidenceBasedExpectations() throws Exception {
        String xml = "<Envelope><Code>  A</Code><Amount>1250</Amount><Date>20240102</Date><Enabled>true</Enabled></Envelope>";
        FormatExample.Value result = mapper.unformat(xml);
        assertEquals("A", result.code());
        assertEquals(new BigDecimal("12.50"), result.amount());
        assertEquals(LocalDate.of(2024, 1, 2), result.date());
        assertTrue(result.enabled());
    }

    @Test public void nullableChildKeepsPopulatedParentAndSiblings() throws Exception {
        String xml = mapper.format(value("ABC", null));
        Element root = root(xml);
        assertFalse(root.hasAttributeNS(XSI, "nil"));
        Element child = (Element) root.getElementsByTagName("Enabled").item(0);
        assertEquals("true", child.getAttributeNS(XSI, "nil"));
        assertEquals("ABC", text(root, "Code"));
        FormatExample.Value result = mapper.unformat(xml);
        assertNotNull(result);
        assertEquals("ABC", result.code());
        assertNull(result.enabled());
    }

    @Test public void evidencedMissingEmptyAndInvalidValuesRemainDistinct() throws Exception {
        String prefix = "<Envelope><Code>ABC</Code><Amount>1250</Amount><Date>20240102</Date>";
        assertNull(mapper.unformat(prefix + "</Envelope>").enabled());
        assertThrows(IllegalArgumentException.class, () -> mapper.unformat(prefix + "<Enabled></Enabled></Envelope>"));
        assertThrows(IllegalArgumentException.class, () -> mapper.unformat(prefix + "<Enabled>invalid</Enabled></Envelope>"));
        assertThrows(NumberFormatException.class, () -> mapper.unformat(prefix.replace("1250", "invalid") + "</Envelope>"));
    }

    @Test public void roundTripIsAdditionalEvidenceRatherThanTheOnlyTest() throws Exception {
        FormatExample.Value original = value("ABC", true);
        assertEquals(original, mapper.unformat(mapper.format(original)));
    }
}
