package il.co.dcd.composermapper.util;
import org.w3c.dom.*; import org.xml.sax.InputSource; import javax.xml.XMLConstants; import javax.xml.parsers.DocumentBuilderFactory; import java.io.StringReader; import java.nio.file.Path; import java.util.*;
public final class XmlUtil {
  private XmlUtil(){}
  public static Document parse(Path path){ try{ var f=DocumentBuilderFactory.newInstance(); f.setNamespaceAware(false); f.setIgnoringComments(true); f.setIgnoringElementContentWhitespace(true); f.setXIncludeAware(false); f.setExpandEntityReferences(false); disableExternalEntities(f); var b=f.newDocumentBuilder(); b.setEntityResolver((publicId,systemId)->new InputSource(new StringReader(""))); var d=b.parse(path.toFile()); d.getDocumentElement().normalize(); return d; }catch(Exception e){ throw new XmlParseException(path,e);} }
  private static void disableExternalEntities(DocumentBuilderFactory f) throws Exception { f.setFeature("http://xml.org/sax/features/external-general-entities", false); f.setFeature("http://xml.org/sax/features/external-parameter-entities", false); f.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false); f.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, ""); f.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, ""); }
  public static String attr(Element e,String n){ return e.hasAttribute(n)?e.getAttribute(n).trim():null; }
  public static List<Element> childElements(Element p){ List<Element> r=new ArrayList<>(); for(int i=0;i<p.getChildNodes().getLength();i++){ Node n=p.getChildNodes().item(i); if(n.getNodeType()==Node.ELEMENT_NODE) r.add((Element)n);} return r; }
}
