package il.co.dcd.composermapper.storage;

import il.co.dcd.javaanalysis.*;
import java.nio.file.*;
import java.util.*;
import javax.xml.stream.*;

/** Persist one bounded AST batch as individual fact rows, not one file/project JSON value. */
final class JavaFactReader {
    private JavaFactReader(){}
    static void analyze(AnalysisStore store,List<SourceSnapshot> batch) throws Exception {
        Path temporary=Files.createTempFile("mapper-java-facts-",".xml");
        try {
            try(var stream=Files.newOutputStream(temporary)) {
                var writer=XMLOutputFactory.newFactory().createXMLStreamWriter(stream,"UTF-8");
                writer.writeStartDocument();writer.writeStartElement("analysis");
                SourceAnalysis.writeBatch(batch,writer);
                writer.writeEndElement();writer.writeEndDocument();writer.close();
            }
            var factory=XMLInputFactory.newFactory();factory.setProperty(XMLInputFactory.SUPPORT_DTD,false);
            try(var stream=Files.newInputStream(temporary)) {
                var reader=factory.createXMLStreamReader(stream);String file=null;int ordinal=0;boolean metadata=false;
                while(reader.hasNext()) {
                    int event=reader.next();
                    if(event==XMLStreamConstants.START_ELEMENT) {
                        String tag=reader.getLocalName();
                        if(tag.equals("source")){file=reader.getAttributeValue(null,"path");ordinal=0;}
                        else if(tag.equals("java_class")) {
                            metadata=true;
                            store.execute("INSERT OR REPLACE INTO java_classes VALUES (?,?,?,?,?)",file,attribute(reader,"fqcn"),
                                store.scalar("SELECT value FROM java_facts WHERE file=? AND kind='package'",file),attribute(reader,"simple_name"),attribute(reader,"parent"));
                        } else if(tag.equals("issue")) {
                            String source=attribute(reader,"path");
                            store.execute("INSERT INTO records(collection,data) VALUES ('java_issues',?)",StoredJson.encode(Map.of("file",source,"message",attribute(reader,"message"))));
                            store.execute("UPDATE files SET complete=-1 WHERE path=?",source);
                        } else if(file!=null&&!tag.equals("analysis")) {
                            String kind=metadata?"metadata:"+tag:tag;
                            String name=tag.equals("return")?attribute(reader,"code"):attribute(reader,"name");
                            String value=tag.equals("return")?attribute(reader,"meaning"):tag.equals("reference")?attribute(reader,"kind"):attribute(reader,"static");
                            String extra=tag.equals("reference")?attribute(reader,"offset"):"";
                            store.execute("INSERT INTO java_facts VALUES (?,?,?,?,?,?)",file,++ordinal,kind,name,value,extra);
                        }
                        if(tag.equals("source"))store.execute("INSERT INTO java_facts VALUES (?,?,?,?,?,?)",file,++ordinal,"package","",attribute(reader,"package"),"");
                    } else if(event==XMLStreamConstants.END_ELEMENT) {
                        if(reader.getLocalName().equals("java_class"))metadata=false;
                        if(reader.getLocalName().equals("source"))store.execute("UPDATE files SET complete=1 WHERE path=? AND complete=0",file);
                    }
                }
                reader.close();
            }
            store.commit();
        } finally {Files.deleteIfExists(temporary);}
    }
    private static String attribute(XMLStreamReader reader,String key){return Objects.requireNonNullElse(reader.getAttributeValue(null,key),"");}
}
