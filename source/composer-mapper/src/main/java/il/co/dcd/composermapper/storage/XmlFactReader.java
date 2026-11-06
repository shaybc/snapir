package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import java.nio.file.*;
import java.util.*;
import javax.xml.stream.*;

/** Parse a captured XML revision once into ordered rows; no workspace DOM survives. */
public final class XmlFactReader {
    private XmlFactReader(){}
    private record Frame(String id,String selector,String owner,boolean insideFormat,SiblingPositions labels,int[] ordinal,int[] elementPosition){}

    public static void read(AnalysisStore store,Path file,Path captured) throws Exception {
        var factory=XMLInputFactory.newFactory();
        factory.setProperty(XMLInputFactory.IS_NAMESPACE_AWARE,false);
        factory.setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES,false);
        factory.setProperty(XMLInputFactory.SUPPORT_DTD,false);
        factory.setProperty(XMLInputFactory.IS_REPLACING_ENTITY_REFERENCES,false);
        factory.setXMLResolver((publicId,systemId,base,namespace)->new java.io.ByteArrayInputStream(new byte[0]));
        ArrayDeque<Frame> stack=new ArrayDeque<>();
        try(var stream=Files.newInputStream(captured)) {
            var reader=factory.createXMLStreamReader(stream);
            while(reader.hasNext()) {
                int event=reader.next();
                // Match the existing DOM reader: declarations are allowed, external
                // resources are never opened and entity-reference bodies stay unexpanded.
                if(event==XMLStreamConstants.DTD||event==XMLStreamConstants.ENTITY_REFERENCE)continue;
                if(event==XMLStreamConstants.START_ELEMENT) {
                    if(stack.size()>=512)throw new IllegalArgumentException("XML depth exceeds analysis limit: "+file);
                    String name=reader.getLocalName(); Frame parent=stack.peek();
                    int ordinal=parent==null?1:++parent.ordinal()[0];
                    int elementPosition=parent==null?1:++parent.elementPosition()[0];
                    int same=parent==null?1:parent.labels().next(name);
                    String selector=(parent==null?"":parent.selector())+"/"+name+"["+same+"]";
                    String id=SourceDefinitionIdentity.digest(file.toString(),selector);
                    String owner=parent==null?"":parent.owner();
                    boolean inside=parent!=null&&parent.insideFormat();
                    store.execute("INSERT INTO xml_nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)",id,file.toString(),parent==null?null:parent.id(),ordinal,1,name,null,selector,owner,inside?1:0,elementPosition);
                    for(int i=0;i<reader.getAttributeCount();i++)store.execute("INSERT INTO xml_attributes VALUES (?,?,?)",id,reader.getAttributeLocalName(i),reader.getAttributeValue(i));
                    stack.push(new Frame(id,selector,name.equals("CCDSEServerOperation")?selector:owner,inside||name.equals("fmtDef"),new SiblingPositions(store,id),new int[]{0},new int[]{0}));
                } else if(event==XMLStreamConstants.END_ELEMENT) stack.pop().labels().close();
                else if((event==XMLStreamConstants.CHARACTERS||event==XMLStreamConstants.CDATA)&&!stack.isEmpty()) {
                    Frame parent=stack.peek(); int ordinal=++parent.ordinal()[0];
                    String id=SourceDefinitionIdentity.digest(parent.id(),"text",Integer.toString(ordinal));
                    store.execute("INSERT INTO xml_nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)",id,file.toString(),parent.id(),ordinal,3,"#text",reader.getText(),parent.selector()+"/text()["+ordinal+"]",parent.owner(),parent.insideFormat()?1:0,0);
                }
            }
            reader.close();
        }
    }
}
