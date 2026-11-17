package com.snapir.format.api;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import javax.xml.namespace.QName;

/**
 * Native XML data shared by independently converted formats. API version: 1.
 *
 * <p>Content is ordered and may mix text and child elements. Strings are logical, unescaped text;
 * serialization escapes them exactly once. Attribute values are likewise unescaped. No XML
 * parsing, rendering, decorator execution or business defaults are implemented by this type.
 *
 * <p>An absent element is represented by a null XmlElement reference. An empty element is a
 * non-null instance with empty content. An explicit empty text value is a content entry "".
 * A nil element retains its actual namespace-qualified nil attribute; it is not collapsed to null.
 * Text whitespace, child order and QName prefixes must not be normalized by consumers.
 *
 * @param name element namespace URI, local name and prefix
 * @param namespaces namespace declarations on this element, keyed by prefix; "" is the default
 * @param attributes attribute names and values, retaining their supplied iteration order
 * @param content ordered String or XmlElement entries; null entries and other types are invalid
 */
public record XmlElement(
        QName name,
        Map<String, String> namespaces,
        Map<QName, String> attributes,
        List<Object> content) {
    /** Snapshot XML structure without changing names, text, order or namespace declarations. */
    public XmlElement {
        Objects.requireNonNull(name, "name");
        namespaces = Collections.unmodifiableMap(new LinkedHashMap<>(Objects.requireNonNull(namespaces, "namespaces")));
        attributes = Collections.unmodifiableMap(new LinkedHashMap<>(Objects.requireNonNull(attributes, "attributes")));
        namespaces.forEach((prefix, uri) -> {
            Objects.requireNonNull(prefix, "namespace prefix");
            Objects.requireNonNull(uri, "namespace URI");
        });
        attributes.forEach((key, value) -> {
            Objects.requireNonNull(key, "attribute name");
            Objects.requireNonNull(value, "attribute value");
        });
        content = List.copyOf(Objects.requireNonNull(content, "content"));
        for (Object item : content) {
            if (!(item instanceof String) && !(item instanceof XmlElement)) {
                throw new IllegalArgumentException("XML content must contain only String or XmlElement entries");
            }
        }
    }
}
