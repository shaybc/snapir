package com.company.generated.support.format;

import java.io.StringReader;
import java.io.StringWriter;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.Element;
import org.xml.sax.InputSource;

/** Native leaf formatter: context value to XML, or XML to a typed context value. */
public abstract class AbstractFieldFormatter<T> {
    private final String dataName;
    private final List<ValueDecorator> decorators;

    protected AbstractFieldFormatter(String dataName, List<ValueDecorator> decorators) {
        this.dataName = Objects.requireNonNull(dataName);
        if (dataName.isBlank()) throw new IllegalArgumentException("A field name is required");
        this.decorators = List.copyOf(decorators);
    }

    /** Serialize first, then apply decorators in declaration order. */
    public final String format(Map<String, Object> context) throws Exception {
        T value = readValue(context);
        String text;
        try {
            text = value == null ? "" : formatValue(value);
        } catch (RuntimeException error) {
            text = onFormatFailure(value, error);
        }
        for (ValueDecorator decorator : decorators) text = decorator.addDecoration(text);
        var document = DocumentBuilderFactory.newInstance().newDocumentBuilder().newDocument();
        Element field = document.createElement(dataName);
        field.setTextContent(text);
        document.appendChild(field);
        var factory = TransformerFactory.newInstance();
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_STYLESHEET, "");
        var transformer = factory.newTransformer();
        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
        StringWriter output = new StringWriter();
        transformer.transform(new DOMSource(document), new StreamResult(output));
        return output.toString();
    }

    /** Read a leaf field; remove decorators in reverse order before parsing its value. */
    public final void unformat(String xml, Map<String, Object> context) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);
        var document = factory.newDocumentBuilder().parse(new InputSource(new StringReader(xml)));
        var fields = document.getElementsByTagName(dataName);
        if (fields.getLength() == 0) return;
        if (fields.getLength() != 1) throw new IllegalArgumentException("Ambiguous field: " + dataName);
        String text = fields.item(0).getTextContent();
        for (int index = decorators.size() - 1; index >= 0; index--) {
            text = decorators.get(index).removeDecoration(text);
        }
        T value;
        try {
            value = unformatValue(text);
        } catch (RuntimeException error) {
            value = onUnformatFailure(text, error);
        }
        writeValue(context, value);
    }

    /** Override these access hooks when adapting a hierarchical native context. */
    @SuppressWarnings("unchecked")
    protected T readValue(Map<String, Object> context) {
        return (T) context.get(dataName);
    }

    protected void writeValue(Map<String, Object> context, T value) {
        context.put(dataName, value);
    }

    protected abstract String formatValue(T value);
    protected abstract T unformatValue(String value);

    /** Subclasses can implement an explicitly documented fallback policy. */
    protected String onFormatFailure(T value, RuntimeException error) {
        throw error;
    }

    protected T onUnformatFailure(String value, RuntimeException error) {
        throw error;
    }
}
