package il.co.dcd.composermapper.util;
import org.w3c.dom.*; import javax.xml.parsers.DocumentBuilderFactory; import java.nio.file.Path; import java.util.*;
public final class XmlUtil {
  private XmlUtil(){}
  public static Document parse(Path path){ try{ var f=DocumentBuilderFactory.newInstance(); f.setNamespaceAware(false); f.setIgnoringComments(true); f.setIgnoringElementContentWhitespace(true); var d=f.newDocumentBuilder().parse(path.toFile()); d.getDocumentElement().normalize(); return d; }catch(Exception e){ throw new RuntimeException("Failed parsing XML: "+path,e);} }
  public static String attr(Element e,String n){ return e.hasAttribute(n)?e.getAttribute(n).trim():null; }
  public static List<Element> childElements(Element p){ List<Element> r=new ArrayList<>(); for(int i=0;i<p.getChildNodes().getLength();i++){ Node n=p.getChildNodes().item(i); if(n.getNodeType()==Node.ELEMENT_NODE) r.add((Element)n);} return r; }
}
