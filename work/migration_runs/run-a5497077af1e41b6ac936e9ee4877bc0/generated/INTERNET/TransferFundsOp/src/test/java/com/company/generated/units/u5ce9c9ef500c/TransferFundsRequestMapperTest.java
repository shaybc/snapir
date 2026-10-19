package com.company.generated.units.u5ce9c9ef500c;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

public class TransferFundsRequestMapperTest {
    @Test
    public void unformatsPaddedFieldsAndNumber() {
        TransferFundsRequestXml xml = new TransferFundsRequestXml();
        xml.sourceAccount = "0000123456";
        xml.targetAccount = "0000654321";
        xml.amount = "1500.50";
        xml.currency = "USD";
        xml.sessionToken = "tok123";
        xml.transferReference = "REF999";
        xml.scheduledDate = "2023-12-31";

        TransferFundsRequestBusiness biz = new TransferFundsRequestMapper().toBusinessInput(xml);

        assertEquals("123456", biz.getSourceAccount());
        assertEquals("654321", biz.getTargetAccount());
        assertEquals(new BigDecimal("1500.50"), biz.getAmount());
        assertEquals("USD", biz.getCurrency());
        assertEquals("tok123", biz.getSessionToken());
        assertEquals("REF999", biz.getTransferReference());
        assertEquals("2023-12-31", biz.getScheduledDate());
    }

    @Test
    public void handlesNullWireSafely() {
        TransferFundsRequestBusiness biz = new TransferFundsRequestMapper().toBusinessInput(null);
        assertNull(biz);
    }
}