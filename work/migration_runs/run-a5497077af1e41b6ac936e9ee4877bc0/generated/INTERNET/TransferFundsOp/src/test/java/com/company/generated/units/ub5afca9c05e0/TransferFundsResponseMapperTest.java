package com.company.generated.units.ub5afca9c05e0;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.io.ByteArrayInputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;

public class TransferFundsResponseMapperTest {
    private final TransferFundsResponseMapper mapper = new TransferFundsResponseMapper();
    private static final String XSI = "http://www.w3.org/2001/XMLSchema-instance";

    private Element parseRoot(String xml) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8))).getDocumentElement();
    }

    private String text(Element root, String name) {
        return root.getElementsByTagName(name).item(0).getTextContent();
    }

    @Test
    public void testFormatAndUnformatTransferFundsResponse() throws Exception {
        TransferFundsResponseBusiness original = new TransferFundsResponseBusiness();
        original.setTransferId("TRX12345");
        original.setTransferStatus("SUCCESS");
        original.setExecutionDate(new Date(0L));
        original.setExecutionTime(new Date(0L));
        original.setAmount(new BigDecimal("150.00"));
        original.setCurrency("USD");
        original.setSourceAccount("12");
        original.setTargetAccount("456");
        original.setNewSourceBalance(new BigDecimal("850.00"));
        original.setFraudCheckSkipped(false);

        String xml = mapper.format(original);
        Element root = parseRoot(xml);

        assertEquals("TransferFundsResponse", root.getTagName());
        assertEquals("TRX12345", text(root, "TransferId"));
        assertEquals("SUCCESS", text(root, "TransferStatus"));
        assertEquals("150.00", text(root, "Amount"));
        assertEquals("USD", text(root, "Currency"));
        assertEquals(" 12", text(root, "SourceAccount"));
        assertEquals("0000000456", text(root, "TargetAccount"));
        assertEquals("850.00", text(root, "NewSourceBalance"));
        assertEquals("false", text(root, "FraudCheckSkipped"));

        TransferFundsResponseBusiness result = mapper.unformat(xml);
        assertEquals("TRX12345", result.getTransferId());
        assertEquals("SUCCESS", result.getTransferStatus());
        assertEquals(new BigDecimal("150.00"), result.getAmount());
        assertEquals("USD", result.getCurrency());
        assertEquals("12", result.getSourceAccount());
        assertEquals("456", result.getTargetAccount());
        assertEquals(new BigDecimal("850.00"), result.getNewSourceBalance());
        assertFalse(result.getFraudCheckSkipped());
    }

    @Test
    public void testNullableFraudCheckSkippedNilDecorator() throws Exception {
        TransferFundsResponseBusiness original = new TransferFundsResponseBusiness();
        original.setTransferId("TRX999");
        original.setTransferStatus("PENDING");
        original.setAmount(new BigDecimal("50.00"));
        original.setCurrency("EUR");
        original.setSourceAccount("123");
        original.setTargetAccount("1234567890");
        original.setFraudCheckSkipped(null);

        String xml = mapper.format(original);
        Element root = parseRoot(xml);

        Element child = (Element) root.getElementsByTagName("FraudCheckSkipped").item(0);
        assertNotNull(child);
        assertEquals("true", child.getAttributeNS(XSI, "nil"));

        TransferFundsResponseBusiness result = mapper.unformat(xml);
        assertNull(result.getFraudCheckSkipped());
    }
}
