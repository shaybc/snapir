package il.co.dcd.javaanalysis;

import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.io.*;
import java.net.URI;
import java.nio.file.*;
import java.util.*;
import javax.tools.*;
import javax.xml.stream.*;

/** Bounded AST lifecycle: all metadata and reference facts come from one parse session. */
public final class SourceAnalysis {
    private SourceAnalysis() {}

    /** Parse at most 100 captured files/4 MiB; oversized individual files form a separate batch. */
    public static void writeBatch(List<SourceSnapshot> sources, XMLStreamWriter output) throws Exception {
        long bytes = sources.stream().mapToLong(s -> s.text().length() * 2L).sum();
        if (sources.size() > 100 || sources.size() > 1 && bytes > 4L * 1024 * 1024)
            throw new IllegalArgumentException("AST batch exceeds bounded analysis limits");
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw new IllegalStateException("Java source analysis requires a JDK");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, null, java.nio.charset.StandardCharsets.UTF_8)) {
            List<JavaFileObject> inputs = new ArrayList<>();
            for (SourceSnapshot source : sources) inputs.add(new SimpleJavaFileObject(source.path().toUri(), JavaFileObject.Kind.SOURCE) {
                @Override public CharSequence getCharContent(boolean ignoreEncodingErrors) { return source.text(); }
            });
            JavacTask task = (JavacTask) compiler.getTask(null, manager, diagnostics, List.of("-proc:none"), null, inputs);
            Trees trees = Trees.instance(task);
            int parsed = 0;
            for (CompilationUnitTree unit : task.parse()) {
                SourceSnapshot source = sources.stream().filter(value -> value.path().toUri().equals(unit.getSourceFile().toUri())).findFirst().orElseThrow();
                parsed++;
                output.writeStartElement("source");
                output.writeAttribute("path", source.path().toString());
                output.writeAttribute("hash", source.hash());
                output.writeAttribute("encoding", source.encoding());
                output.writeAttribute("package", unit.getPackageName() == null ? "" : unit.getPackageName().toString());
                for (ImportTree imported : unit.getImports()) {
                    output.writeEmptyElement("import");
                    output.writeAttribute("name", imported.getQualifiedIdentifier().toString());
                    output.writeAttribute("static", Boolean.toString(imported.isStatic()));
                }
                new ReferenceCollector(unit, trees, output).scan(unit, null);
                JavaMetadataExtractor.write(unit, source, output);
                output.writeEndElement();
                output.flush();
                System.out.println("Parsed " + parsed + "/" + sources.size() + " Java files; collected metadata and references.");
                System.out.println("Scanned references in " + parsed + "/" + sources.size() + " Java files.");
            }
            for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() != Diagnostic.Kind.ERROR) continue;
                output.writeEmptyElement("issue");
                output.writeAttribute("path", diagnostic.getSource() == null ? "" : Paths.get(diagnostic.getSource().toUri()).toString());
                output.writeAttribute("message", diagnostic.getMessage(Locale.ROOT));
            }
        }
    }
}
