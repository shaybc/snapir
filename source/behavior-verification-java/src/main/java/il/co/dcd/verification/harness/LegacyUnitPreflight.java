package il.co.dcd.verification.harness;

import java.nio.file.Path;
import java.util.*;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;

/** Check original public interfaces without class initialization or business execution. */
public final class LegacyUnitPreflight {
    private LegacyUnitPreflight() { }
    private static Class<?> type(String name)throws Exception{return Class.forName(name,false,Thread.currentThread().getContextClassLoader());}
    public static void main(String[] args)throws Exception {
        var factory=DocumentBuilderFactory.newInstance();factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        Element job=factory.newDocumentBuilder().parse(Path.of(args[0]).toFile()).getDocumentElement();
        Class<?> context=type(job.getAttribute("context")),tag=type(job.getAttribute("tag")),owner=type(job.getAttribute("owner"));
        context.getConstructor();tag.getConstructor(Map.class);
        context.getMethod(job.getAttribute("writer"),String.class,Object.class);context.getMethod(job.getAttribute("snapshot"));
        var nodes=job.getElementsByTagName("type");
        for(int i=0;i<nodes.getLength();i++) {
            Element node=(Element)nodes.item(i);Class<?> element=type(node.getAttribute("name"));element.getConstructor();
            if(Arrays.stream(element.getMethods()).anyMatch(m->m.getName().equals("initializeFrom")))element.getMethod("initializeFrom",tag);
            else {
                var attributes=node.getElementsByTagName("attribute");
                for(int j=0;j<attributes.getLength();j++) {
                    String name=((Element)attributes.item(j)).getAttribute("name");
                    if(Arrays.stream(element.getMethods()).filter(m->m.getName().equalsIgnoreCase("set"+name)&&Arrays.equals(m.getParameterTypes(),new Class<?>[]{String.class})).count()!=1)
                        throw new IllegalArgumentException("Unsupported initialization attribute: "+element.getName()+"."+name);
                }
            }
        }
        switch(job.getAttribute("action")) {
            case "format" -> owner.getMethod("format",context);
            case "unformat" -> owner.getMethod("unformat",String.class,context);
            case "addDecoration", "removeDecoration" -> owner.getMethod(job.getAttribute("action"),String.class);
            case "formatXmlAttributes" -> owner.getMethod("formatXmlAttributes",context,String.class);
            default -> throw new IllegalArgumentException("Unsupported original action");
        }
        checkChildren(BoundaryValues.children(BoundaryValues.child(job,"configuration"),null).get(0));
    }
    private static void checkChildren(Element node)throws Exception {
        Class<?> owner=type(node.getAttribute("implementation"));
        for(Element child:BoundaryValues.children(node,null)) {
            if(!Set.of("component","decorator").contains(child.getTagName()))continue;
            Class<?> target=type(child.getAttribute("implementation"));
            Set<String> names=child.getTagName().equals("decorator")?Set.of("addDecorator","addAttributeDecorator"):Set.of("addChild");
            if(Arrays.stream(owner.getMethods()).filter(m->names.contains(m.getName())&&m.getParameterCount()==1&&m.getParameterTypes()[0].isAssignableFrom(target)).count()!=1)
                throw new IllegalArgumentException("Unsupported/ambiguous child registration: "+owner.getName()+" -> "+target.getName());
            checkChildren(child);
        }
    }
}
