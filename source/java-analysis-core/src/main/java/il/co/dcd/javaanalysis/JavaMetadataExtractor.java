package il.co.dcd.javaanalysis;

import com.sun.source.tree.*;
import com.sun.source.util.TreeScanner;
import java.util.*;
import java.util.regex.*;
import javax.xml.stream.*;

/** Preserve Mapper's documentary metadata while deriving declarations from the shared AST. */
final class JavaMetadataExtractor {
    private static final Pattern JAVADOC = Pattern.compile("(?s)/\\*\\*(.*?)\\*/");
    private static final Pattern RETURN_DOC = Pattern.compile("(?i)(?:returns?\\s*)?(-?\\d+)\\s*(?:\\(([^)]+)\\)|[-:=]\\s*([^,;\\n\\r.]+))");

    private JavaMetadataExtractor() {}

    static void write(CompilationUnitTree unit, SourceSnapshot source, XMLStreamWriter output) throws XMLStreamException {
        ClassTree primary = unit.getTypeDecls().stream().filter(t -> t instanceof ClassTree)
            .map(t -> (ClassTree)t).findFirst().orElse(null);
        if (primary == null) return;
        String pkg = unit.getPackageName() == null ? "" : unit.getPackageName().toString();
        String name = primary.getSimpleName().toString(), fqcn = pkg.isEmpty() ? name : pkg + "." + name;
        Map<String,String> imports = new LinkedHashMap<>(), constants = new LinkedHashMap<>();
        Set<String> methods = new LinkedHashSet<>(), setters = new LinkedHashSet<>(), exceptions = new LinkedHashSet<>();
        Map<String,Set<String>> returns = new LinkedHashMap<>();
        for (ImportTree imported : unit.getImports()) {
            String value = imported.getQualifiedIdentifier().toString();
            if (!imported.isStatic()) imports.put(value.substring(value.lastIndexOf('.') + 1), value);
        }
        new TreeScanner<Void,Void>() {
            @Override public Void visitVariable(VariableTree node, Void ignored) {
                var flags = node.getModifiers().getFlags();
                if (flags.contains(javax.lang.model.element.Modifier.STATIC) && flags.contains(javax.lang.model.element.Modifier.FINAL)
                        && node.getType().toString().equals("int") && node.getInitializer() != null) {
                    String value = node.getInitializer().toString().replace(" ", "");
                    if (value.matches("-?\\d+")) constants.put(node.getName().toString(), value);
                }
                return super.visitVariable(node, ignored);
            }
        }.scan(unit, null);
        Matcher documents = JAVADOC.matcher(source.text());
        while (documents.find()) {
            Matcher codes = RETURN_DOC.matcher(documents.group(1));
            while (codes.find()) {
                String meaning = codes.group(2) != null ? codes.group(2) : codes.group(3);
                if (meaning != null) returns.computeIfAbsent(codes.group(1), key -> new LinkedHashSet<>()).add(meaning.trim());
            }
        }
        new TreeScanner<Void,Void>() {
            private final Deque<String> classes=new ArrayDeque<>();
            @Override public Void visitClass(ClassTree node,Void ignored){classes.push(node.getSimpleName().toString());try{return super.visitClass(node,ignored);}finally{classes.pop();}}
            @Override public Void visitMethod(MethodTree node, Void ignored) {
                String method = node.getName().toString();
                if(method.equals("<init>")&&!classes.isEmpty())method=classes.peek();
                if (!method.isEmpty()) {
                    methods.add(method);
                    if (method.startsWith("set") && method.length() > 3) setters.add(method);
                    node.getThrows().forEach(type -> exceptions.add(type.toString()));
                }
                return super.visitMethod(node, ignored);
            }
            @Override public Void visitReturn(ReturnTree node, Void ignored) {
                if (node.getExpression() != null) {
                    String value = node.getExpression().toString().replace(" ", "");
                    if (value.matches("-?\\d+")) returns.computeIfAbsent(value, key -> new LinkedHashSet<>());
                    else if (constants.containsKey(value)) returns.computeIfAbsent(constants.get(value), key -> new LinkedHashSet<>())
                        .add(value.toLowerCase(Locale.ROOT).replace('_',' '));
                }
                return super.visitReturn(node, ignored);
            }
            @Override public Void visitThrow(ThrowTree node, Void ignored) {
                if (node.getExpression() instanceof NewClassTree created) exceptions.add(created.getIdentifier().toString());
                return super.visitThrow(node, ignored);
            }
        }.scan(unit, null);
        output.writeStartElement("java_class");
        output.writeAttribute("simple_name", name); output.writeAttribute("fqcn", fqcn);
        output.writeAttribute("parent", primary.getExtendsClause() == null ? "" : resolve(primary.getExtendsClause().toString(), pkg, imports));
        for (Tree type : primary.getImplementsClause()) item(output,"interface",resolve(type.toString(),pkg,imports));
        for (String method : methods) item(output,"method",method);
        for (String setter : setters) item(output,"setter",setter);
        for (String exception : exceptions) item(output,"exception",exception);
        for (var code : returns.entrySet()) {
            if (code.getValue().isEmpty()) returnCode(output, code.getKey(), "");
            else for (String meaning : code.getValue()) returnCode(output, code.getKey(), meaning);
        }
        Set<String> external = new LinkedHashSet<>();
        for (String value : imports.values()) {
            if (value.startsWith("com.ibm")) external.add("IBM/WAS");
            if (value.contains("java.sql") || value.contains("javax.sql") || value.contains("JdbcTemplate") || value.contains("DataSource")) external.add("Database");
            if (value.contains("HttpClient") || value.contains("RestTemplate") || value.contains("WebClient") || value.contains("HttpURLConnection")) external.add("API/Service");
        }
        for (String value : external) item(output,"external",value);
        String lower=source.text().toLowerCase(Locale.ROOT), type=fqcn.toLowerCase(Locale.ROOT);
        Set<String> behaviors=new LinkedHashSet<>();
        if (contains(lower,"java.sql","callablestatement","preparestatement","storedprocedure","jdbctemplate")) behaviors.add("db_accessor");
        if (contains(type,"error","maperror") || contains(lower,"errorcategory","errornumber")) behaviors.add("error_mapper");
        if (contains(type,"validator","validate") || contains(lower,"mandatory","isnull")) behaviors.add("validator");
        if (contains(type,"format","decorator") || setters.stream().anyMatch(s -> contains(s,"Pattern","DataName","Sep"))) behaviors.add("formatter");
        if (contains(type,"collect","icoll","coll")) behaviors.add("collector");
        if (behaviors.isEmpty()) behaviors.add("unknown");
        for (String value : behaviors) item(output,"behavior",value);
        output.writeEndElement();
    }

    private static boolean contains(String text, String... values) { return Arrays.stream(values).anyMatch(text::contains); }
    private static String resolve(String value, String pkg, Map<String,String> imports) {
        String name=value.split("[<,\\s]")[0];
        return name.contains(".") ? name : imports.getOrDefault(name, pkg.isEmpty() ? name : pkg + "." + name);
    }
    private static void item(XMLStreamWriter output,String tag,String name) throws XMLStreamException {
        output.writeEmptyElement(tag); output.writeAttribute("name",name);
    }
    private static void returnCode(XMLStreamWriter output,String code,String meaning) throws XMLStreamException {
        output.writeEmptyElement("return"); output.writeAttribute("code",code); output.writeAttribute("meaning",meaning);
    }
}
