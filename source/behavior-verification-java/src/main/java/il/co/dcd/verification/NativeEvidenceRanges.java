package il.co.dcd.verification;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.*;
import org.w3c.dom.*;

/** Exact declaration ranges for focused evidence; no execution or semantic summaries. */
final class NativeEvidenceRanges {
    private NativeEvidenceRanges() { }
    static void inspect(Document doc,Element root,CompilationUnit unit,String source,String path) {
        for(var node:unit.findAll(BodyDeclaration.class)) {
            if(!(node instanceof CallableDeclaration<?> || node instanceof FieldDeclaration || node instanceof InitializerDeclaration))continue;
            if(node.getRange().isEmpty())continue;
            var range=node.getRange().orElseThrow();
            var entry=doc.createElement("evidence-range");root.appendChild(entry);
            entry.setAttribute("source",source);entry.setAttribute("path",path);
            entry.setAttribute("kind",node.getClass().getSimpleName());
            entry.setAttribute("start_line",String.valueOf(range.begin.line));
            entry.setAttribute("end_line",String.valueOf(range.end.line));
            entry.setAttribute("name",node instanceof CallableDeclaration<?> c?c.getNameAsString():"declaration");
        }
    }
}
