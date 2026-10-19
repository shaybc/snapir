package example.format;

import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Objects;

/** Illustrative rules only: width three, implied two decimals, basic ISO date and nullable child. */
public final class FormatExample {
    private final XmlMapper mapper;

    public FormatExample() {
        mapper = new XmlMapper();
        // XML-specific features belong to ToXmlGenerator, not SerializationFeature.
        mapper.configure(ToXmlGenerator.Feature.WRITE_XML_DECLARATION, false);
    }

    public record Value(String code, BigDecimal amount, LocalDate date, Boolean enabled) {}

    @JacksonXmlRootElement(localName = "Envelope")
    public static class Wire {
        @JacksonXmlProperty(localName = "Code") public String code;
        @JacksonXmlProperty(localName = "Amount") public String amount;
        @JacksonXmlProperty(localName = "Date") public String date;
        @JacksonXmlProperty(localName = "Enabled") public NullableText enabled;
    }

    /** A nil attribute belongs to this child element, never to the populated envelope. */
    public static class NullableText {
        @JacksonXmlText public String value;
        @JacksonXmlProperty(localName = "nil", isAttribute = true,
            namespace = "http://www.w3.org/2001/XMLSchema-instance") public String nil;
    }

    public String format(Value value) throws Exception {
        Objects.requireNonNull(value, "Example requires a populated root");
        Wire wire = new Wire();
        String code = Objects.requireNonNull(value.code());
        wire.code = code.length() < 3 ? " ".repeat(3 - code.length()) + code : code;
        wire.amount = value.amount().movePointRight(2).toBigIntegerExact().toString();
        wire.date = value.date().format(DateTimeFormatter.BASIC_ISO_DATE);
        wire.enabled = new NullableText();
        if (value.enabled() == null) {
            wire.enabled.nil = "true";
        } else {
            wire.enabled.value = value.enabled().toString();
        }
        return mapper.writeValueAsString(wire);
    }

    public Value unformat(String xml) throws Exception {
        Wire wire = mapper.readValue(xml, Wire.class);
        Objects.requireNonNull(wire, "Example requires a populated root");
        Boolean enabled = null;
        if (wire.enabled != null && !"true".equals(wire.enabled.nil)) {
            if (!"true".equals(wire.enabled.value) && !"false".equals(wire.enabled.value)) {
                throw new IllegalArgumentException("Expected true, false or a nil child");
            }
            enabled = Boolean.valueOf(wire.enabled.value);
        }
        return new Value(wire.code.replaceFirst("^ +", ""),
            new BigDecimal(wire.amount).movePointLeft(2),
            LocalDate.parse(wire.date, DateTimeFormatter.BASIC_ISO_DATE), enabled);
    }
}
