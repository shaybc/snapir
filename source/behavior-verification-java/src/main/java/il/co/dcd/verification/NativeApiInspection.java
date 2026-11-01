package il.co.dcd.verification;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.MethodCallExpr;
import java.nio.file.*;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.*;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.*;

/** Parse native public APIs without executing code or requiring resolved external libraries. */
public final class NativeApiInspection {
    private NativeApiInspection() { }

    public static void main(String[] args) throws Exception {
        var factory=DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        var input=factory.newDocumentBuilder().parse(Path.of(args[0]).toFile());
        var output=factory.newDocumentBuilder().newDocument();
        var root=output.createElement("native-api"); output.appendChild(root);
        var parser=new JavaParser(new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE));
        var files=input.getDocumentElement().getElementsByTagName("file");
        var originals=input.getDocumentElement().getElementsByTagName("original");
        for(int i=0;i<originals.getLength();i++) {
            var source=(Element)originals.item(i);var result=parser.parse(source.getTextContent());
            if(!result.isSuccessful())throw new IllegalArgumentException("Original Java parse failed: "+source.getAttribute("identity"));
            NativeEvidenceRanges.inspect(output,root,result.getResult().orElseThrow(),source.getAttribute("identity"),"");
            for(var type:result.getResult().orElseThrow().findAll(ClassOrInterfaceDeclaration.class)) {
                for(var method:type.getMethods()) {
                    if(!method.isPublic() || !method.isStatic())continue;
                    var entry=add(output,root,"original-method","target",type.getFullyQualifiedName().orElse(type.getNameAsString())+"."+method.getNameAsString());
                    entry.setAttribute("source",source.getAttribute("identity"));
                    for(var parameter:method.getParameters()) {
                        var p=add(output,entry,"parameter","name",parameter.getNameAsString());p.setAttribute("type",parameter.getTypeAsString());
                    }
                }
            }
            for(var call:result.getResult().orElseThrow().findAll(MethodCallExpr.class)) {
                if(!java.util.Set.of("getValueAt","setValueAt","removeValueAt").contains(call.getNameAsString()) || call.getArguments().isEmpty())continue;
                if(call.getArgument(0).isStringLiteralExpr()) {
                    var key=add(output,root,"context-key","name",call.getArgument(0).asStringLiteralExpr().asString());
                    key.setAttribute("source",source.getAttribute("identity"));key.setAttribute("method",call.getNameAsString());
                }
            }
        }
        for(int i=0;i<files.getLength();i++) {
            var file=(Element)files.item(i); var result=parser.parse(file.getTextContent());
            if(!result.isSuccessful())throw new IllegalArgumentException("Native parse failed: "+file.getAttribute("path")+result.getProblems());
            var unit=result.getResult().orElseThrow();
            NativeEvidenceRanges.inspect(output,root,unit,"",file.getAttribute("path"));
            var node=add(output,root,"file","path",file.getAttribute("path"));
            node.setAttribute("package",unit.getPackageDeclaration().map(p->p.getNameAsString()).orElse(""));
            for(var imp:unit.getImports()) {
                var entry=add(output,node,"import","name",imp.getNameAsString());
                entry.setAttribute("wildcard",String.valueOf(imp.isAsterisk()));
                entry.setAttribute("static",String.valueOf(imp.isStatic()));
            }
            NativeTestCalls.inspect(output,node,unit);
            for(var type:unit.getTypes())inspect(output,node,type,node.getAttribute("package"),false);
        }
        TransformerFactory.newInstance().newTransformer().transform(new DOMSource(output),new StreamResult(Path.of(args[1]).toFile()));
    }

    private static void inspect(Document doc,Element parent,TypeDeclaration<?> type,String prefix,boolean implicit) {
        String name=prefix.isEmpty()?type.getNameAsString():prefix+"."+type.getNameAsString();
        var node=add(doc,parent,"type","name",name);
        boolean enclosingPublic=!parent.getTagName().equals("type") || parent.getAttribute("public").equals("true");
        node.setAttribute("public",String.valueOf(enclosingPublic && !type.isPrivate() && !type.isProtected() && (type.isPublic() || implicit)));
        node.setAttribute("simple",type.getNameAsString());
        node.setAttribute("kind",type.getClass().getSimpleName());
        boolean iface=type instanceof ClassOrInterfaceDeclaration ci && ci.isInterface();
        node.setAttribute("interface",String.valueOf(iface));
        if(type instanceof ClassOrInterfaceDeclaration ci) {
            for(var parameter:ci.getTypeParameters())add(doc,node,"type-parameter","name",parameter.getNameAsString());
            for(var base:ci.getExtendedTypes())add(doc,node,"parent","type",base.toString());
            for(var base:ci.getImplementedTypes())add(doc,node,"parent","type",base.toString());
        }
        int constructors=0;
        for(var member:type.getMembers()) {
            if(member instanceof ConstructorDeclaration ctor) {
                constructors++;
                if(ctor.isPublic())callable(doc,node,ctor,"constructor",ctor.getDeclarationAsString(true,false,true),type.getNameAsString());
            } else if(member instanceof MethodDeclaration method && !method.isPrivate() && !method.isProtected() && (method.isPublic() || iface)) {
                var entry=callable(doc,node,method,"method",method.getDeclarationAsString(true,false,true),method.getNameAsString());
                entry.setAttribute("returns",method.getTypeAsString());
                entry.setAttribute("static",String.valueOf(method.isStatic()));
                entry.setAttribute("abstract",String.valueOf(method.isAbstract() || iface && !method.isDefault() && !method.isStatic()));
            } else if(member instanceof TypeDeclaration<?> nested)inspect(doc,node,nested,name,iface);
            else if(member instanceof FieldDeclaration field) {
                for(var variable:field.getVariables()) {
                    var entry=add(doc,node,"field","name",variable.getNameAsString());
                    entry.setAttribute("type",variable.getTypeAsString());
                    entry.setAttribute("public",String.valueOf(field.isPublic() || iface));
                }
            }
        }
        if(type instanceof RecordDeclaration record) {
            var ctor=add(doc,node,"constructor","name",type.getNameAsString());ctor.setAttribute("implicit","true");
            for(var parameter:record.getParameters()) {
                var p=add(doc,ctor,"parameter","name",parameter.getNameAsString());p.setAttribute("type",parameter.getTypeAsString());
                var getter=add(doc,node,"method","name",parameter.getNameAsString());getter.setAttribute("returns",parameter.getTypeAsString());getter.setAttribute("implicit","true");getter.setAttribute("static","false");
            }
        } else if(constructors==0 && type instanceof ClassOrInterfaceDeclaration ci && !ci.isInterface()) {
            var ctor=add(doc,node,"constructor","name",type.getNameAsString());ctor.setAttribute("implicit","true");
        }
    }

    private static Element callable(Document doc,Element parent,CallableDeclaration<?> member,String tag,String signature,String name) {
        var entry=add(doc,parent,tag,"name",name);entry.setAttribute("signature",signature);
        for(var parameter:member.getParameters()) {
            var p=add(doc,entry,"parameter","name",parameter.getNameAsString());
            p.setAttribute("type",parameter.getTypeAsString()+(parameter.isVarArgs()?"[]":""));
        }
        return entry;
    }

    private static Element add(Document doc,Element parent,String tag,String key,String value) {
        var entry=doc.createElement(tag);entry.setAttribute(key,value);parent.appendChild(entry);return entry;
    }
}
