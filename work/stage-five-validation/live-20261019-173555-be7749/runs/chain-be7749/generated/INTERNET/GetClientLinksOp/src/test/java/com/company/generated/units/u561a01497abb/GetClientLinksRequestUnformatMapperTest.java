package com.company.generated.units.u561a01497abb;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GetClientLinksRequestUnformatMapperTest {
    private final GetClientLinksRequestUnformatMapper mapper = new GetClientLinksRequestUnformatMapper();

    @Test
    public void unformatsValidRequestWithPaddingAndMandatoryFields() throws Exception {
        String xml = "<GetClientLinks><ClientId>12345</ClientId><BankId>0012</BankId></GetClientLinks>";
        GetClientLinksRequest req = mapper.unformat(xml);
        assertNotNull(req);
        assertEquals("12345", req.getClientId());
        assertEquals("12", req.getBankId());
    }

    @Test
    public void throwsExceptionWhenMandatoryClientIdIsMissing() {
        String xml = "<GetClientLinks><BankId>0012</BankId></GetClientLinks>;";
        assertThrows(Exception.class, () -> mapper.unformat(xml));
    }

    @Test
    public void unformatsBankIdWithoutLeadingZerosIfShorterOrExact() throws Exception {
        String xml = "<GetClientLinks><ClientId>C999</ClientId><BankId>0005</BankId></GetClientLinks>";
        GetClientLinksRequest req = mapper.unformat(xml);
        assertEquals("C999", req.getClientId());
        assertEquals("5", req.getBankId());
    }

    @Test
    public void handlesDirectBusinessInputMapping() {
        GetClientLinksRequestXml wire = new GetClientLinksRequestXml();
        wire.clientId = "ABC";
        wire.bankId = "0123";
        GetClientLinksRequest req = mapper.toBusinessInput(wire);
        assertEquals("ABC", req.getClientId());
        assertEquals("123", req.getBankId());
    }
}
