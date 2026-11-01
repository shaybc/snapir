package com.ibm.il.dse.cc.format;

import java.io.StringReader;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/** Demo XML fragment access, preserving nested elements for container formatters. */
final class DemoXml {
    private DemoXml() { }

    static String value(String xml, String name) {
        if (xml == null) return null;
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            Element root = factory.newDocumentBuilder().parse(new InputSource(new StringReader("<demo>" + xml + "</demo>"))).getDocumentElement();
            for (Node node = root.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (node instanceof Element && node.getNodeName().equals(name)) {
                    StringBuilder inner = new StringBuilder();
                    for (Node child = node.getFirstChild(); child != null; child = child.getNextSibling()) {
                        if (child instanceof Element) {
                            javax.xml.transform.Transformer transformer = javax.xml.transform.TransformerFactory.newInstance().newTransformer();
                            transformer.setOutputProperty(javax.xml.transform.OutputKeys.OMIT_XML_DECLARATION, "yes");
                            java.io.StringWriter writer = new java.io.StringWriter();
                            transformer.transform(new javax.xml.transform.dom.DOMSource(child), new javax.xml.transform.stream.StreamResult(writer));
                            inner.append(writer);
                        } else inner.append(child.getTextContent());
                    }
                    return inner.toString();
                }
            }
            return null;
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid demo XML", exception);
        }
    }

    static String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }

    static java.util.List<String> elements(String xml, String name) {
        java.util.List<String> result = new java.util.ArrayList<>();
        if (xml == null) return result;
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            Element root = factory.newDocumentBuilder().parse(new InputSource(new StringReader("<demo>" + xml + "</demo>"))).getDocumentElement();
            for (Node node = root.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (node instanceof Element && node.getNodeName().equals(name)) {
                    javax.xml.transform.Transformer transformer = javax.xml.transform.TransformerFactory.newInstance().newTransformer();
                    transformer.setOutputProperty(javax.xml.transform.OutputKeys.OMIT_XML_DECLARATION, "yes");
                    java.io.StringWriter writer = new java.io.StringWriter();
                    transformer.transform(new javax.xml.transform.dom.DOMSource(node), new javax.xml.transform.stream.StreamResult(writer));
                    result.add(writer.toString());
                }
            }
            return result;
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid demo XML", exception);
        }
    }
}
