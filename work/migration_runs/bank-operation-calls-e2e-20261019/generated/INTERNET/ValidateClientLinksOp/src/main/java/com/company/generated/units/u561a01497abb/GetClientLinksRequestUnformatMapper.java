package com.company.generated.units.u561a01497abb;

import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator;
import java.util.Objects;

public class GetClientLinksRequestUnformatMapper {
    private final XmlMapper xmlMapper;

    public GetClientLinksRequestUnformatMapper() {
        this.xmlMapper = new XmlMapper();
        this.xmlMapper.configure(ToXmlGenerator.Feature.WRITE_XML_DECLARATION, false);
    }

    public GetClientLinksRequest toBusinessInput(GetClientLinksRequestXml wire) {
        Objects.requireNonNull(wire, "Wire model cannot be null");

        // CCMandatory validation on ClientId
        if (wire.clientId == null || wire.clientId.trim().isEmpty()) {
            throw new IllegalArgumentException("ClientId is mandatory");
        }

        // CCPadding unformat on BankId: padChar='0', length=4 -> strip leading '0' characters (padLeft=true)
        String bankId = wire.bankId;
        if (bankId != null) {
            bankId = bankId.replaceFirst("^0+", "");
        }

        return new GetClientLinksRequest(wire.clientId, bankId);
    }

    public GetClientLinksRequest unformat(String xml) throws Exception {
        GetClientLinksRequestXml wire = xmlMapper.readValue(xml, GetClientLinksRequestXml.class);
        return toBusinessInput(wire);
    }
}
