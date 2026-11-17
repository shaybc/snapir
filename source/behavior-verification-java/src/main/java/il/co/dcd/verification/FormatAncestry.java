package il.co.dcd.verification;

import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import java.util.HashSet;
import java.util.Set;

/** Classify formats by the real IBM base type, without executing workspace code. */
final class FormatAncestry {
    private FormatAncestry() { }

    static boolean isFormat(ResolvedReferenceTypeDeclaration declaration) {
        return inherits(declaration, new HashSet<>());
    }

    private static boolean inherits(ResolvedReferenceTypeDeclaration declaration, Set<String> seen) {
        String name = declaration.getQualifiedName();
        if (!seen.add(name)) return false;
        if (name.equals("com.ibm.dse.base.FormatElement")) return true;
        for (var ancestor : declaration.getAncestors()) {
            if (ancestor.getTypeDeclaration().isPresent()
                    && inherits(ancestor.getTypeDeclaration().get(), seen)) return true;
        }
        return false;
    }
}
