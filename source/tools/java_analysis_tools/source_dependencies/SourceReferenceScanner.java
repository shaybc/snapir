// Parse syntax only: no annotation processors, symbol attribution, or user-code execution.
import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.tools.*;
import javax.xml.parsers.*;
import javax.xml.stream.*;
import org.w3c.dom.*;

/** Emit structured type/reference sites from a batch of original Java sources. */
public class SourceReferenceScanner {
    public static void main(String[] args) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Document manifest = factory.newDocumentBuilder().parse(new File(args[0]));
        List<File> files = new ArrayList<>();
        NodeList nodes = manifest.getElementsByTagName("source");
        for (int i = 0; i < nodes.getLength(); i++) {
            files.add(new File(((Element) nodes.item(i)).getAttribute("path")));
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw new IllegalStateException("Java source analysis requires a JDK");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, null, java.nio.charset.StandardCharsets.UTF_8);
             OutputStream stream = Files.newOutputStream(Paths.get(args[1]))) {
            JavacTask task = (JavacTask) compiler.getTask(null, manager, diagnostics,
                    Arrays.asList("-proc:none", "-encoding", "UTF-8"), null, manager.getJavaFileObjectsFromFiles(files));
            XMLStreamWriter output = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
            output.writeStartDocument();
            output.writeStartElement("analysis");
            Trees trees = Trees.instance(task);
            for (CompilationUnitTree unit : task.parse()) {
                output.writeStartElement("source");
                output.writeAttribute("path", Paths.get(unit.getSourceFile().toUri()).toString());
                output.writeAttribute("package", unit.getPackageName() == null ? "" : unit.getPackageName().toString());
                for (ImportTree imported : unit.getImports()) {
                    output.writeEmptyElement("import");
                    output.writeAttribute("name", imported.getQualifiedIdentifier().toString());
                    output.writeAttribute("static", Boolean.toString(imported.isStatic()));
                }
                new References(unit, trees, output).scan(unit, null);
                output.writeEndElement();
            }
            for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() != Diagnostic.Kind.ERROR) continue;
                output.writeEmptyElement("issue");
                output.writeAttribute("path", diagnostic.getSource() == null ? "" : Paths.get(diagnostic.getSource().toUri()).toString());
                output.writeAttribute("message", diagnostic.getMessage(Locale.ROOT));
            }
            output.writeEndElement();
            output.writeEndDocument();
            output.close();
        }
    }

    private static class References extends TreeScanner<Void, Void> {
        private final CompilationUnitTree unit;
        private final Trees trees;
        private final XMLStreamWriter output;
        private final Set<String> emitted = new HashSet<>();

        References(CompilationUnitTree unit, Trees trees, XMLStreamWriter output) {
            this.unit = unit;
            this.trees = trees;
            this.output = output;
        }

        private void reference(Tree tree, String name, String kind) {
            if (tree == null || name == null || name.isEmpty()) return;
            long offset = trees.getSourcePositions().getStartPosition(unit, tree);
            if (!emitted.add(offset + ":" + name)) return;
            element("reference", "name", name, "kind", kind, "offset", Long.toString(offset));
        }

        private void element(String tag, String... attributes) {
            try {
                output.writeEmptyElement(tag);
                for (int i = 0; i < attributes.length; i += 2) output.writeAttribute(attributes[i], attributes[i + 1]);
            } catch (XMLStreamException error) {
                throw new IllegalStateException(error);
            }
        }

        private void type(Tree tree) {
            if (tree == null) return;
            new TreeScanner<Void, Void>() {
                @Override public Void visitIdentifier(IdentifierTree value, Void ignored) {
                    reference(value, value.getName().toString(), "type"); return null;
                }
                @Override public Void visitMemberSelect(MemberSelectTree value, Void ignored) {
                    reference(value, value.toString(), "type"); return null;
                }
            }.scan(tree, null);
        }

        @Override public Void visitImport(ImportTree tree, Void ignored) { return null; }
        @Override public Void visitCompilationUnit(CompilationUnitTree tree, Void ignored) {
            return scan(tree.getTypeDecls(), ignored);
        }
        @Override public Void visitVariable(VariableTree tree, Void ignored) {
            element("variable", "name", tree.getName().toString());
            type(tree.getType()); return super.visitVariable(tree, ignored);
        }
        @Override public Void visitMethod(MethodTree tree, Void ignored) {
            element("method", "name", tree.getName().toString());
            type(tree.getReturnType());
            for (ExpressionTree value : tree.getThrows()) type(value);
            return super.visitMethod(tree, ignored);
        }
        @Override public Void visitClass(ClassTree tree, Void ignored) {
            element("local_type", "name", tree.getSimpleName().toString());
            type(tree.getExtendsClause());
            for (Tree value : tree.getImplementsClause()) type(value);
            for (Tree value : tree.getPermitsClause()) type(value);
            return super.visitClass(tree, ignored);
        }
        @Override public Void visitTypeParameter(TypeParameterTree tree, Void ignored) {
            element("type_parameter", "name", tree.getName().toString());
            for (Tree bound : tree.getBounds()) type(bound);
            return super.visitTypeParameter(tree, ignored);
        }
        @Override public Void visitNewClass(NewClassTree tree, Void ignored) {
            type(tree.getIdentifier()); return super.visitNewClass(tree, ignored);
        }
        @Override public Void visitNewArray(NewArrayTree tree, Void ignored) {
            type(tree.getType()); return super.visitNewArray(tree, ignored);
        }
        @Override public Void visitTypeCast(TypeCastTree tree, Void ignored) {
            type(tree.getType()); return super.visitTypeCast(tree, ignored);
        }
        @Override public Void visitInstanceOf(InstanceOfTree tree, Void ignored) {
            type(tree.getType()); return super.visitInstanceOf(tree, ignored);
        }
        @Override public Void visitAnnotation(AnnotationTree tree, Void ignored) {
            type(tree.getAnnotationType()); return super.visitAnnotation(tree, ignored);
        }
        @Override public Void visitMethodInvocation(MethodInvocationTree tree, Void ignored) {
            if (tree.getMethodSelect() instanceof IdentifierTree) {
                reference(tree.getMethodSelect(), tree.getMethodSelect().toString(), "static_member");
            }
            for (Tree argument : tree.getTypeArguments()) type(argument);
            return super.visitMethodInvocation(tree, ignored);
        }
        @Override public Void visitMemberSelect(MemberSelectTree tree, Void ignored) {
            reference(tree, tree.getExpression().toString(), "qualifier");
            return super.visitMemberSelect(tree, ignored);
        }
        @Override public Void visitMemberReference(MemberReferenceTree tree, Void ignored) {
            reference(tree, tree.getQualifierExpression().toString(), "qualifier");
            return super.visitMemberReference(tree, ignored);
        }
        @Override public Void visitIdentifier(IdentifierTree tree, Void ignored) {
            reference(tree, tree.getName().toString(), "static_field");
            return null;
        }
    }
}
