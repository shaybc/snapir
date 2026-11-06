package il.co.dcd.javaanalysis;
import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.util.*;
import javax.xml.stream.*;
/** Canonical syntax-only reference visitor shared by mapper and converter. */
final class ReferenceCollector extends TreeScanner<Void, Void> {
    private final CompilationUnitTree unit;
    private final Trees trees;
    private final XMLStreamWriter output;
    private final Set<String> emitted = new HashSet<>();

    ReferenceCollector(CompilationUnitTree unit, Trees trees, XMLStreamWriter output) {
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
