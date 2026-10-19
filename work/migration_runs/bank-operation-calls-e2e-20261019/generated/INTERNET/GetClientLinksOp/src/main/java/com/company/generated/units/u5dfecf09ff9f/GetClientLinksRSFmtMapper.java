package com.company.generated.units.u5dfecf09ff9f;

import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlElementWrapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public final class GetClientLinksRSFmtMapper {
    private final XmlMapper xmlMapper;

    public GetClientLinksRSFmtMapper() {
        this.xmlMapper = new XmlMapper();
        this.xmlMapper.configure(ToXmlGenerator.Feature.WRITE_XML_DECLARATION, false);
    }

    public static class LinkDescriptionWire {
        @JacksonXmlText
        public String value;

        @JacksonXmlProperty(localName = "nil", isAttribute = true, namespace = "http://www.w3.org/2001/XMLSchema-instance")
        public String nil;
    }

    public static class LinkWire {
        @JacksonXmlProperty(localName = "LinkId")
        public String linkId;

        @JacksonXmlProperty(localName = "LinkDescription")
        public LinkDescriptionWire linkDescription;

        @JacksonXmlProperty(localName = "LinkUrl")
        public String linkUrl;

        @JacksonXmlProperty(localName = "IsExternal")
        public String isExternal;

        @JacksonXmlProperty(localName = "IconCode")
        public LinkDescriptionWire iconCode;
    }

    @JacksonXmlRootElement(localName = "GetClientLinksResponse")
    public static class GetClientLinksResponseWire {
        @JacksonXmlProperty(localName = "ClientId")
        public String clientId;

        @JacksonXmlProperty(localName = "Links")
        public LinksWrapper links;
    }

    public static class LinksWrapper {
        @JacksonXmlElementWrapper(useWrapping = false)
        @JacksonXmlProperty(localName = "Link")
        public List<LinkWire> linkList = new ArrayList<>();
    }

    public record LinkDto(String linkId, String linkDescription, String linkUrl, Boolean isExternal, String iconCode) {}

    public record GetClientLinksResponse(String clientId, List<LinkDto> links) {}

    public String format(GetClientLinksResponse response) throws Exception {
        Objects.requireNonNull(response, "Response cannot be null");
        GetClientLinksResponseWire wire = new GetClientLinksResponseWire();
        wire.clientId = response.clientId();
        if (response.links() != null) {
            wire.links = new LinksWrapper();
            for (LinkDto dto : response.links()) {
                LinkWire lw = new LinkWire();
                if (dto.linkId() == null || dto.linkId().isEmpty()) {
                    throw new IllegalArgumentException("LinkId is mandatory");
                }
                lw.linkId = dto.linkId();

                lw.linkDescription = new LinkDescriptionWire();
                if (dto.linkDescription() == null || dto.linkDescription().isBlank()) {
                    lw.linkDescription.nil = "true";
                } else {
                    lw.linkDescription.value = dto.linkDescription();
                }

                lw.linkUrl = dto.linkUrl();

                if (dto.isExternal() != null) {
                    lw.isExternal = dto.isExternal() ? "true" : "false";
                }

                lw.iconCode = new LinkDescriptionWire();
                if (dto.iconCode() == null || dto.iconCode().isBlank()) {
                    lw.iconCode.nil = "true";
                } else {
                    lw.iconCode.value = dto.iconCode();
                }

                wire.links.linkList.add(lw);
            }
        }
        return xmlMapper.writeValueAsString(wire);
    }

    public GetClientLinksResponse unformat(String xml) throws Exception {
        Objects.requireNonNull(xml, "XML cannot be null");
        GetClientLinksResponseWire wire = xmlMapper.readValue(xml, GetClientLinksResponseWire.class);
        if (wire == null) {
            return null;
        }
        List<LinkDto> dtos = new ArrayList<>();
        if (wire.links != null && wire.links.linkList != null) {
            for (LinkWire lw : wire.links.linkList) {
                if (lw.linkId == null || lw.linkId.isEmpty()) {
                    throw new IllegalArgumentException("LinkId is mandatory");
                }
                String desc = null;
                if (lw.linkDescription != null && !"true".equals(lw.linkDescription.nil)) {
                    desc = lw.linkDescription.value;
                }
                String url = lw.linkUrl;
                Boolean isExt = null;
                if (lw.isExternal != null) {
                    isExt = Boolean.valueOf(lw.isExternal);
                }
                String icon = null;
                if (lw.iconCode != null && !"true".equals(lw.iconCode.nil)) {
                    icon = lw.iconCode.value;
                }
                dtos.add(new LinkDto(lw.linkId, desc, url, isExt, icon));
            }
        }
        return new GetClientLinksResponse(wire.clientId, dtos);
    }
}
