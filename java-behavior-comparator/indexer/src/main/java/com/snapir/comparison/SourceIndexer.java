package com.snapir.comparison;
import com.fasterxml.jackson.databind.*;
import com.github.javaparser.*;
import com.github.javaparser.ast.*;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import com.github.javaparser.symbolsolver.resolution.typesolvers.*;
import java.nio.file.*;
import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.util.*;
import java.util.jar.JarFile;

/** Read-only AST inventory with exact source spans; no application class is loaded or executed. */
public final class SourceIndexer {
    private final Map<String,Object> chunks=new TreeMap<>(), classes=new TreeMap<>();
    private final List<String> warnings=new ArrayList<>();
    private final ObjectMapper json=new ObjectMapper();
    public static void main(String[] args) throws Exception {
        var index=new SourceIndexer(); var input=index.json.readTree(Path.of(args[0]).toFile());
        for (var file:input.path("sources")) index.source(file);
        var binary=index.archives(input.path("jars"));
        index.json.writerWithDefaultPrettyPrinter().writeValue(Path.of(args[1]).toFile(),
            Map.of("classes",index.classes,"chunks",index.chunks,"warnings",index.warnings,"binary",binary));
    }
    private void source(JsonNode file) {
        String path=file.path("path").asText(), side=file.path("side").asText();
        try {
            String text=Files.readString(Path.of(path),Charset.forName(file.path("encoding").asText())).replaceFirst("^\\uFEFF","");
            var parsed=new JavaParser(new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE)).parse(text);
            if (!parsed.isSuccessful()) {warnings.add(path+": "+parsed.getProblems());return;}
            var unit=parsed.getResult().orElseThrow();
            var jdkImports=new TreeMap<String,String>();
            var platform=new ClassLoaderTypeSolver(ClassLoader.getPlatformClassLoader());
            var simpleNames=new TreeSet<String>();
            unit.findAll(com.github.javaparser.ast.type.ClassOrInterfaceType.class).forEach(t -> simpleNames.add(t.getNameWithScope()));
            unit.findAll(NameExpr.class).forEach(n -> simpleNames.add(n.getNameAsString()));
            for (String simple:simpleNames) {
                var candidates=new ArrayList<String>();candidates.add("java.lang."+simple);
                for (var imported:unit.getImports()) if (!imported.isStatic() && imported.getNameAsString().startsWith("java."))
                    candidates.add(imported.isAsterisk()?imported.getNameAsString()+"."+simple:imported.getNameAsString());
                for (String candidate:candidates) if (candidate.endsWith("."+simple) && platform.tryToSolveType(candidate).isSolved())
                    jdkImports.put(simple,candidate);
            }
            for (TypeDeclaration<?> type:unit.findAll(TypeDeclaration.class)) {
                if (type.findAncestor(CallableDeclaration.class).isPresent()) continue;
                String name=type.getFullyQualifiedName().orElse(""); if (name.isBlank()) continue;
                String key=side+"::"+name;
                if (classes.containsKey(key)) {warnings.add("Ambiguous class: "+key);continue;}
                var parents=new ArrayList<String>();
                if (type instanceof ClassOrInterfaceDeclaration declaration) {
                    declaration.getExtendedTypes().forEach(p -> parents.add(p.getNameWithScope()));
                    declaration.getImplementedTypes().forEach(p -> parents.add(p.getNameWithScope()));
                }
                var members=new ArrayList<String>();var fields=new TreeMap<String,String>();
                if (type instanceof RecordDeclaration record)
                    record.getParameters().forEach(p -> fields.put(p.getNameAsString(),p.getTypeAsString()));
                for (var field:type.getFields()) {
                    for (var variable:field.getVariables()) fields.put(variable.getNameAsString(),variable.getTypeAsString());
                    members.add(chunk(field,"field",field.getVariables().toString(),name,side,path,text));
                }
                for (var member:type.getMembers()) {
                    if (member instanceof MethodDeclaration method)
                        members.add(chunk(method,"method",method.getDeclarationAsString(),name,side,path,text));
                    else if (member instanceof ConstructorDeclaration constructor)
                        members.add(chunk(constructor,"constructor",constructor.getDeclarationAsString(),name,side,path,text));
                    else if (member instanceof InitializerDeclaration initializer)
                        members.add(chunk(initializer,"initializer",initializer.isStatic()?"static initializer":"instance initializer",name,side,path,text));
                }
                if (members.isEmpty() || type instanceof RecordDeclaration || type instanceof EnumDeclaration)
                    members.add(chunk(type,"type",name,name,side,path,text));
                var record=new LinkedHashMap<String,Object>();
                record.put("name",name);record.put("side",side);record.put("file",path);record.put("parents",parents);
                record.put("imports",unit.getImports().stream().map(Object::toString).toList());
                record.put("fields",fields);record.put("members",members);
                record.put("jdk_imports",jdkImports);
                classes.put(key,record);
            }
        } catch (Exception error) {warnings.add(path+": "+error.getClass().getSimpleName()+": "+error.getMessage());}
    }
    private String chunk(Node node,String kind,String signature,String owner,String side,String path,String text) throws Exception {
        var range=node.getRange().orElseThrow();
        String id=side+"/"+HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(
            (path+"|"+signature+"|"+range.begin).getBytes(java.nio.charset.StandardCharsets.UTF_8))).substring(0,24);
        String[] lines=text.split("\\R",-1);
        String[] selected=Arrays.copyOfRange(lines,range.begin.line-1,range.end.line);
        selected[selected.length-1]=selected[selected.length-1].substring(0,range.end.column);
        selected[0]=selected[0].substring(range.begin.column-1);
        String source=String.join("\n",selected);
        var facts=new TreeMap<String,Object>();var calls=new ArrayList<Map<String,Object>>();var variables=new TreeMap<String,String>();
        node.findAll(Parameter.class).forEach(p -> variables.put(p.getNameAsString(),p.getTypeAsString()));
        node.findAll(VariableDeclarator.class).forEach(v -> variables.put(v.getNameAsString(),v.getTypeAsString()));
        for (Node child:node.findAll(Node.class)) {
            String category=null;
            if (child instanceof IfStmt || child instanceof SwitchEntry || child instanceof ConditionalExpr) category="branch";
            else if (child instanceof ReturnStmt) category="return";
            else if (child instanceof ThrowStmt || child instanceof CatchClause) category="exception";
            else if (child instanceof AssignExpr || child instanceof VariableDeclarator) category="write_or_initialization";
            else if (child instanceof ForStmt || child instanceof ForEachStmt || child instanceof WhileStmt || child instanceof DoStmt) category="loop";
            else if (child instanceof MethodCallExpr call) {
                category="call";
                calls.add(Map.of("name",call.getNameAsString(),"scope",call.getScope().map(Object::toString).orElse(""),"arity",call.getArguments().size()));
            } else if (child instanceof ObjectCreationExpr creation) {
                category="construction";
                calls.add(Map.of("name","<init>","scope",creation.getType().getNameWithScope(),"arity",creation.getArguments().size()));
            }
            if (category!=null && child.getBegin().isPresent()) {
                var position=child.getBegin().get();String fact=id+"/"+category+"@"+position.line+":"+position.column;
                facts.put(fact,Map.of("id",fact,"kind",category,"line",position.line,"column",position.column));
            }
        }
        String name=kind;
        if (node instanceof MethodDeclaration method) name=method.getNameAsString();
        if (node instanceof ConstructorDeclaration) name="<init>";
        var record=new LinkedHashMap<String,Object>();
        record.put("id",id);record.put("side",side);record.put("owner",owner);record.put("kind",kind);record.put("name",name);
        record.put("signature",signature);record.put("file",path);record.put("line",range.begin.line);record.put("end_line",range.end.line);
        record.put("source",source);record.put("facts",facts.values());record.put("calls",calls);record.put("variables",variables);
        record.put("arity",node instanceof CallableDeclaration<?> callable?callable.getParameters().size():0);
        record.put("parameter_types",node instanceof CallableDeclaration<?> callable?
            callable.getParameters().stream().map(p -> p.getTypeAsString()).toList():List.of());
        record.put("public_api",node instanceof MethodDeclaration method && !method.isPrivate());
        chunks.put(id,record);return id;
    }
    private List<Object> archives(JsonNode inputs) {
        var result=new ArrayList<Object>();
        for (var input:inputs) {
            String path=input.path("path").asText(), side=input.path("side").asText();
            try (var jar=new JarFile(path)) {
                var names=jar.stream().filter(e -> e.getName().endsWith(".class"))
                    .map(e -> e.getName().replace('/','.').replaceAll("\\.class$","")).toList();
                var solver=new CombinedTypeSolver(new ClassLoaderTypeSolver(ClassLoader.getPlatformClassLoader()),new JarTypeSolver(path));
                var signatures=new TreeMap<String,Object>();
                for (Object item:classes.values()) {
                    var type=(Map<?,?>)item;
                    if (!side.equals(type.get("side"))) continue;
                    for (Object parent:(Collection<?>)type.get("parents")) {
                        String candidate=parent.toString();
                        if (!names.contains(candidate)) {
                            List<String> matches=names.stream().filter(n -> n.endsWith("."+parent)).toList();
                            if (matches.size()==1) candidate=matches.get(0);else continue;
                        }
                        try {
                            var resolved=solver.solveType(candidate);
                            signatures.put(candidate,Map.of("methods",resolved.getDeclaredMethods().stream().map(m -> m.getQualifiedSignature()).toList(),
                                "source_available",false));
                        } catch (RuntimeException error) {warnings.add("Binary metadata unavailable: "+candidate);}
                    }
                }
                result.add(Map.of("path",path,"side",side,"classes",names,"signatures",signatures));
            } catch (Exception error) {warnings.add("Unreadable archive "+path+": "+error.getMessage());}
        }
        return result;
    }
}
