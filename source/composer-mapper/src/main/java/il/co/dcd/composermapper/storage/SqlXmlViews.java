package il.co.dcd.composermapper.storage;

import java.lang.reflect.*;
import java.nio.file.Path;
import java.util.*;
import org.w3c.dom.*;

/** Read-only DOM interfaces over indexed XML facts, reusing stable Mapper extraction rules. */
public final class SqlXmlViews implements InvocationHandler {
    private final AnalysisStore store;
    private final String id;
    private final String file;
    private final short type;
    private final String name;
    private SqlXmlViews(AnalysisStore store,String id,String file,short type,String name){this.store=store;this.id=id;this.file=file;this.type=type;this.name=name;}

    public static Document document(AnalysisStore store,Path file){return (Document)Proxy.newProxyInstance(SqlXmlViews.class.getClassLoader(),new Class[]{Document.class},new SqlXmlViews(store,null,file.toString(),Node.DOCUMENT_NODE,"#document"));}
    public static String identity(Element element){return element==null?null:((SqlXmlViews)Proxy.getInvocationHandler(element)).id;}
    public static List<Element> elements(Element element){
        var view=(SqlXmlViews)Proxy.getInvocationHandler(element);
        var values=view.store.sequence("xml_nodes","parent=? AND type=1",new Object[]{view.id},"id",row->(Element)node(view.store,row[0]));
        int count=values.size();
        return new AbstractList<>() {
            public int size(){return count;}
            public Element get(int index){if(index<0||index>=count)throw new IndexOutOfBoundsException(index);return (Element)view.related("SELECT id FROM xml_nodes WHERE parent=? AND element_position=?",view.id,index+1);}
            public Iterator<Element> iterator(){return values.iterator();}
            public Spliterator<Element> spliterator(){return values.spliterator();}
        };
    }
    public static Node node(AnalysisStore store,String id){
        var row=store.rows("SELECT file,type,name FROM xml_nodes WHERE id=?",id);
        if(row.isEmpty())return null;
        var value=row.getFirst();short kind=Short.parseShort(value[1]);
        return (Node)Proxy.newProxyInstance(SqlXmlViews.class.getClassLoader(),new Class[]{kind==Node.ELEMENT_NODE?Element.class:Text.class},
            new SqlXmlViews(store,id,value[0],kind,value[2]));
    }
    private String scalar(String sql,Object...args){return store.scalar(sql,args);}
    private String value(String column){return id==null?null:scalar("SELECT "+column+" FROM xml_nodes WHERE id=?",id);}
    private Node related(String sql,Object...args){String key=scalar(sql,args);return key==null?null:node(store,key);}
    private NodeList children(){
        String condition=id==null?"file=? AND parent IS NULL":"parent=?";String key=id==null?file:id;
        int count=Integer.parseInt(scalar("SELECT count(*) FROM xml_nodes WHERE "+condition,key));
        return new NodeList(){public int getLength(){return count;}public Node item(int index){return index<0||index>=count?null:related("SELECT id FROM xml_nodes WHERE "+condition+" AND ordinal=?",key,index+1);}};
    }
    private NamedNodeMap attributes(){
        var rows=store.rows("SELECT name,value FROM xml_attributes WHERE node=? ORDER BY name",id);
        List<Node> values=new ArrayList<>();
        for(var row:rows)values.add((Node)Proxy.newProxyInstance(SqlXmlViews.class.getClassLoader(),new Class[]{Attr.class},(proxy,method,args)->switch(method.getName()){
            case "getName","getNodeName","getLocalName" -> row[0];case "getValue","getNodeValue","getTextContent" -> row[1];
            case "getNodeType" -> Node.ATTRIBUTE_NODE;case "getSpecified" -> true;case "getOwnerElement" -> node(store,id);
            case "toString" -> row[0]+"="+row[1];default -> null;
        }));
        return new NamedNodeMap(){
            public int getLength(){return values.size();}public Node item(int index){return index<0||index>=values.size()?null:values.get(index);}
            public Node getNamedItem(String key){return values.stream().filter(n->n.getNodeName().equals(key)).findFirst().orElse(null);}
            public Node getNamedItemNS(String ns,String local){return getNamedItem(local);}
            public Node setNamedItem(Node node){throw new UnsupportedOperationException("Immutable XML facts");}
            public Node removeNamedItem(String key){throw new UnsupportedOperationException("Immutable XML facts");}
            public Node setNamedItemNS(Node node){return setNamedItem(node);}public Node removeNamedItemNS(String ns,String local){return removeNamedItem(local);}
        };
    }

    public Object invoke(Object proxy,Method method,Object[] args) {
        return switch(method.getName()) {
            case "getNodeType" -> type;
            case "getNodeName","getTagName","getLocalName" -> name;
            case "getNodeValue","getData" -> value("value");
            case "getDocumentElement" -> related("SELECT id FROM xml_nodes WHERE file=? AND parent IS NULL ORDER BY ordinal LIMIT 1",file);
            case "getChildNodes" -> children();
            case "hasChildNodes" -> children().getLength()>0;
            case "getFirstChild" -> children().item(0);
            case "getLastChild" -> children().item(children().getLength()-1);
            case "getParentNode" -> related("SELECT parent FROM xml_nodes WHERE id=?",id);
            case "getNextSibling" -> related("SELECT id FROM xml_nodes WHERE parent=? AND ordinal>? ORDER BY ordinal LIMIT 1",value("parent"),value("ordinal"));
            case "getPreviousSibling" -> related("SELECT id FROM xml_nodes WHERE parent=? AND ordinal<? ORDER BY ordinal DESC LIMIT 1",value("parent"),value("ordinal"));
            case "getOwnerDocument" -> document(store,Path.of(file));
            case "getAttributes" -> attributes();
            case "hasAttributes" -> attributes().getLength()>0;
            case "getAttribute" -> Objects.requireNonNullElse(scalar("SELECT value FROM xml_attributes WHERE node=? AND name=?",id,args[0]),"");
            case "hasAttribute" -> scalar("SELECT value FROM xml_attributes WHERE node=? AND name=?",id,args[0])!=null;
            case "getAttributeNode" -> attributes().getNamedItem((String)args[0]);
            case "getTextContent" -> textContent();
            case "getNamespaceURI","getPrefix","getBaseURI","getUserData" -> null;
            case "isSameNode","isEqualNode","equals" -> args[0]!=null&&Proxy.isProxyClass(args[0].getClass())&&Proxy.getInvocationHandler(args[0]) instanceof SqlXmlViews other&&Objects.equals(id,other.id)&&file.equals(other.file);
            case "hashCode" -> Objects.hash(file,id);
            case "toString" -> name+"#"+id;
            case "normalize","setUserData" -> null;
            default -> throw new UnsupportedOperationException("Immutable SQL XML view: "+method.getName());
        };
    }

    private String textContent(){
        if(type==Node.TEXT_NODE)return value("value");
        StringBuilder result=new StringBuilder();
        var children=children();for(int i=0;i<children.getLength();i++) {
            String text=children.item(i).getTextContent();
            if(result.length()+text.length()>4*1024*1024)throw new IllegalStateException("XML text field exceeds bounded view limit");
            result.append(text);
        }
        return result.toString();
    }
}
