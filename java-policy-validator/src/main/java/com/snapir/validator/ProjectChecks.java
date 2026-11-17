package com.snapir.validator;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.*;
import org.xml.sax.InputSource;
import org.xml.sax.helpers.DefaultHandler;
import java.io.StringReader;
import java.util.*;
import java.util.regex.*;

/** Inspect Maven declarations and runtime registrations without Maven execution. */
final class ProjectChecks {
    static void check(String file,String text,Report report) throws Exception {
        if (file.contains("META-INF/services/")) {
            reference(file,file.substring(file.indexOf("META-INF/services/")+18),0,report);
            int line = 0;
            for (String value : text.split("\\R")) {
                line++;
                String name = value.split("#",2)[0].trim();
                if (!name.isEmpty()) reference(file,name,line,report);
            }
        }
        if (!file.endsWith(".xml")) return;
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities",false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities",false);
        factory.setXIncludeAware(false); factory.setExpandEntityReferences(false);
        var builder = factory.newDocumentBuilder(); builder.setErrorHandler(new DefaultHandler());
        Document document;
        try { document = builder.parse(new InputSource(new StringReader(text))); }
        catch (Exception error) {
            report.add("xml_syntax",file,0,"",error.getMessage(),"Return valid XML without external entities or DTDs.");return;
        }
        if (file.endsWith("pom.xml")) maven(file,document,report);
        var nodes = document.getElementsByTagName("*");
        for (int i=0;i<nodes.getLength();i++) {
            var element = (Element)nodes.item(i);
            var attrs = element.getAttributes();
            for (int j=0;j<attrs.getLength();j++) {
                var attr = attrs.item(j);
                if (Set.of("class","implClass","type","provider","factory-class").contains(attr.getNodeName()))
                    reference(file,attr.getNodeValue(),0,report);
            }
        }
    }
    private static String child(Element element,String name) {
        for (Node node=element.getFirstChild();node!=null;node=node.getNextSibling())
            if (node instanceof Element e && e.getTagName().equals(name)) return e.getTextContent().trim();
        return "";
    }
    private static void maven(String file,Document document,Report report) {
        var properties = new HashMap<String,String>();
        var root = document.getDocumentElement();
        for (String key : List.of("groupId","artifactId","version")) {
            properties.put("project."+key,child(root,key)); properties.put("pom."+key,child(root,key));
        }
        var props = document.getElementsByTagName("properties");
        for (int i=0;i<props.getLength();i++)
            for (Node node=props.item(i).getFirstChild();node!=null;node=node.getNextSibling())
                if (node instanceof Element e) properties.put(e.getTagName(),e.getTextContent().trim());
        String expanded = document.getDocumentElement().getTextContent();
        for (int round=0;round<20;round++) {
            String previous = expanded;
            for (var entry:properties.entrySet()) expanded=expanded.replace("${"+entry.getKey()+"}",entry.getValue());
            if (previous.equals(expanded)) break;
        }
        if (expanded.contains("${")) report.add("unresolved_maven_property",file,0,"${...}",
            "Maven properties could not be resolved locally.","Supply explicit locally defined property values.");
        for (String tag : List.of("dependency","plugin","extension","parent","repository","pluginRepository")) {
            var entries = document.getElementsByTagName(tag);
            for (int i=0;i<entries.getLength();i++) {
                var entry = (Element) entries.item(i);
                String group=child(entry,"groupId"), artifact=child(entry,"artifactId"), version=child(entry,"version");
                if (tag.equals("plugin") && group.isEmpty()) group="org.apache.maven.plugins";
                for (int round=0;round<20;round++) for (var value:properties.entrySet()) {
                    group=group.replace("${"+value.getKey()+"}",value.getValue());
                    artifact=artifact.replace("${"+value.getKey()+"}",value.getValue());
                    version=version.replace("${"+value.getKey()+"}",value.getValue());
                }
                String coordinate=group+":"+artifact+":"+version;
                if (tag.endsWith("epository")) {
                    String url=child(entry,"url");
                    if (!report.allowed("allowed_repositories",url)) report.add("maven_repository",file,0,url,
                        "Repository is not explicitly allowed.","Remove it or approve its exact URL in the validator policy.");
                    continue;
                }
                boolean pinned=version.matches("[0-9][A-Za-z0-9_.+-]*") && !version.toUpperCase(Locale.ROOT).contains("SNAPSHOT");
                String allowKey=tag.equals("dependency")?"allowed_dependencies":"allowed_plugins";
                if (report.matches("forbidden_packages",group) || !pinned || !report.allowed(allowKey,coordinate)
                    || tag.equals("parent") || tag.equals("extension"))
                    report.add("maven_dependency_policy",file,0,coordinate,"Unapproved or unpinned Maven "+tag,
                        "Use exact approved native coordinates; remove framework artifacts, parents and build extensions.");
                if (!child(entry,"systemPath").isEmpty() || child(entry,"scope").equals("system"))
                    report.add("maven_system_dependency",file,0,coordinate,"Local JAR dependency cannot be verified.","Use an approved pinned native dependency.");
            }
        }
    }
    private static void reference(String file,String name,int line,Report report) {
        if (report.matches("forbidden_packages",name)) report.add("runtime_registration",file,line,name,
            "Runtime registration references a prohibited framework.","Register an explicit native implementation.");
    }
}
