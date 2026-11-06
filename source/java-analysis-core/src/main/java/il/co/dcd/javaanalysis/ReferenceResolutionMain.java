package il.co.dcd.javaanalysis;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.util.*;
import javax.xml.parsers.*;
import javax.xml.stream.*;
import org.w3c.dom.*;

/** Bounded framed document batches for the converter's compatibility resolver; one reusable worker. */
public final class ReferenceResolutionMain {
    private static final int MAX_FRAME=4*1024*1024;
    private ReferenceResolutionMain(){}
    public static void main(String[] args)throws Exception {
        Class.forName("org.sqlite.JDBC");
        var input=new DataInputStream(new BufferedInputStream(System.in));var output=new DataOutputStream(new BufferedOutputStream(System.out));
        String database=null;Connection connection=null;IndexedTypeLookup lookup=null;
        try {
            while(true) {
                String selected;
                try{selected=frame(input);}catch(EOFException end){break;}
                String source=frame(input);
                if(!selected.equals(database)) {
                    if(lookup!=null)lookup.close();if(connection!=null)connection.close();
                    connection=DriverManager.getConnection("jdbc:sqlite:"+selected);
                    try(var statement=connection.createStatement()){statement.execute("PRAGMA cache_size=-8192");statement.execute("PRAGMA temp_store=FILE");}
                    lookup=new IndexedTypeLookup(connection);database=selected;
                }
                byte[] result=resolve(source,lookup);output.writeInt(result.length);output.write(result);output.flush();
            }
        }finally{if(lookup!=null)lookup.close();if(connection!=null)connection.close();}
    }
    private static String frame(DataInputStream input)throws IOException {
        int size=input.readInt();if(size<0||size>MAX_FRAME)throw new IOException("Java resolution frame exceeds 4 MiB");
        byte[] bytes=input.readNBytes(size);if(bytes.length!=size)throw new EOFException("Truncated Java resolution frame");return new String(bytes,StandardCharsets.UTF_8);
    }
    private static byte[] resolve(String text,IndexedTypeLookup lookup)throws Exception {
        var factory=DocumentBuilderFactory.newInstance();factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities",false);factory.setFeature("http://xml.org/sax/features/external-parameter-entities",false);
        factory.setAttribute(javax.xml.XMLConstants.ACCESS_EXTERNAL_DTD,"");factory.setAttribute(javax.xml.XMLConstants.ACCESS_EXTERNAL_SCHEMA,"");
        Element document=factory.newDocumentBuilder().parse(new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8))).getDocumentElement();
        List<SourceReferenceResolver.Imported> imports=new ArrayList<>();Map<String,Set<String>> symbols=new HashMap<>();
        for(String kind:List.of("variable","type_parameter","local_type","method"))symbols.put(kind,new HashSet<>());
        for(Node child=document.getFirstChild();child!=null;child=child.getNextSibling())if(child instanceof Element element) {
            String kind=element.getTagName();if(kind.equals("import"))imports.add(new SourceReferenceResolver.Imported(element.getAttribute("name"),element.getAttribute("static").equals("true")));
            else if(symbols.containsKey(kind))symbols.get(kind).add(element.getAttribute("name"));
        }
        String path=document.getAttribute("path");lookup.owner(path,document.getAttribute("override_owner").equals("true"),document.hasAttribute("owner_project")?document.getAttribute("owner_project"):null);
        var scope=new SourceReferenceResolver.Scope(path,document.getAttribute("package"),imports,symbols.get("variable"),symbols.get("type_parameter"),symbols.get("local_type"),symbols.get("method"));
        var buffer=new ByteArrayOutputStream();var writer=XMLOutputFactory.newFactory().createXMLStreamWriter(buffer,"UTF-8");writer.writeStartElement("resolution");int completed=0;
        for(Node child=document.getFirstChild();child!=null;child=child.getNextSibling())if(child instanceof Element reference&&reference.getTagName().equals("reference")) {
            var result=SourceReferenceResolver.resolve(reference.getAttribute("name"),reference.getAttribute("kind"),scope,lookup);
            writer.writeStartElement("reference");for(String key:List.of("name","kind","offset"))writer.writeAttribute(key,reference.getAttribute(key));
            if(result.issue()!=null)writer.writeAttribute("issue",result.issue());
            for(String target:result.targets()){writer.writeEmptyElement("target");writer.writeAttribute("path",target);}
            writer.writeEndElement();
            if(++completed%250==0){writer.flush();if(buffer.size()>MAX_FRAME)throw new IOException("Resolution response exceeds 4 MiB");System.err.println("Resolved "+completed+" reference sites.");}
        }
        writer.writeEndElement();writer.close();if(buffer.size()>MAX_FRAME)throw new IOException("Resolution response exceeds 4 MiB");return buffer.toByteArray();
    }
}
