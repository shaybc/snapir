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
        Objects.requireNonNull(wire, "Wire object cannot be null");

        // CCMandatory: clientId must be present and not empty
        if (wire.clientId == null || wire.clientId.isEmpty()) {
            throw new IllegalArgumentException("ClientId is mandatory and cannot be empty");
        }

        // CCPadding on BankId: padChar='0', length=4, padLeft=true by default
        // unformat: remove padding characters (strip leading '0's based on CCPadding unformat logic)
        String bankId = wire.bankId;
        if (bankId != null) {
            bankId = bankId.replaceFirst("^['0']+", "");
            // Alternatively using exact regex quote for '0'
            bankId = bankId.replaceFirst("^[" + java.util.regex.Pattern.quote("0") + "]+", "");
        }

        return new GetClientLinksRequest(wire.clientId, bankId);
    }

    public GetClientLinksRequest unformat(String xml) throws Exception {
        GetClientLinksRequestXml wire = xmlMapper.readValue(xml, GetClientLinksRequestXml.class);
        return toBusinessInput(wire);
    }
}
