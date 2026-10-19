package com.company.generated.units.u561a01497abb;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GetClientLinksRequestUnformatMapperTest {
    private final GetClientLinksRequestUnformatMapper mapper = new GetClientLinksRequestUnformatMapper();

    @Test
    public void unformatsValidRequestXml() throws Exception {
        String xml = "<GetClientLinks><ClientId>12345</ClientId><BankId>0012</BankId></GetClientLinks>";
        GetClientLinksRequest req = mapper.unformat(xml);
        assertNotNull(req);
        assertEquals("12345", req.getClientId());
        assertEquals("12", req.getBankId());
    }

    @Test
    public void failsWhenClientIdIsMissingOrEmpty() {
        GetClientLinksRequestXml wire = new GetClientLinksRequestXml();
        wire.clientId = "   ";
        wire.bankId = "0012";
        assertThrows(IllegalArgumentException.class, () -> mapper.toBusinessInput(wire));
    }

    @Test
    public void stripsPaddingCorrectlyFromBankId() throws Exception {
        String xml = "<GetClientLinks><ClientId>C001</ClientId><BankId>0005</BankId></GetClientLinks>";
        GetClientLinksRequest req = mapper.unformat(xml);
        assertEquals("5", req.getBankId());
    }
}
