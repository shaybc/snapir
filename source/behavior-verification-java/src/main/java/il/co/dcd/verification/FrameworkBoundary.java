package il.co.dcd.verification;

import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import org.w3c.dom.Element;

/** Find a unique public binary-framework entry without imposing source-only signature recipes. */
final class FrameworkBoundary {
    private FrameworkBoundary() { }

    static ResolvedMethodDeclaration entry(Element entry, SourceScope sources, ResolvedReferenceTypeDeclaration type) {
        boolean framework = sources.frameworkTypes.containsKey(type.getQualifiedName())
            || type.getAllAncestors().stream().anyMatch(parent -> sources.frameworkTypes.containsKey(parent.getQualifiedName()));
        if (!framework || !FormatLifecycle.format(entry)) return null;
        var candidates = FormatLifecycle.methods(entry, sources);
        var context = FormatLifecycle.contextEntry(candidates, entry.getAttribute("kind").equals("request_unformat"));
        if (context != null) {
            // Use the same wrapper preference as source-backed formats, preserving basic field entries.
            var preferred = FormatLifecycle.fallback(entry, sources);
            if (preferred != null && preferred.getQualifiedSignature().equals(context.getQualifiedSignature())) return context;
        }
        var methods = candidates.stream()
            .filter(method -> method.getName().equals(entry.getAttribute("method")) && !method.isStatic()
                && method.accessSpecifier() == com.github.javaparser.ast.AccessSpecifier.PUBLIC).toList();
        // Multiple overloads remain an actual binding ambiguity; never choose arbitrarily.
        return methods.size() == 1 ? methods.get(0) : null;
    }
}
