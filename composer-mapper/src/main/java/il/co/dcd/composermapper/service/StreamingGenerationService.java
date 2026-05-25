package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.*;
import il.co.dcd.composermapper.parser.*;
import il.co.dcd.composermapper.render.*;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.XmlParseException;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;

public class StreamingGenerationService {

    private final OperationFileParser   opParser;
    private final FormatFileParser      fmtParser;
    private final ContextFileParser     ctxParser;
    private final JavaClassParser       javaParser;
    private final OperationMarkdownWriter  opWriter;
    private final OpStepMarkdownWriter     stepWriter;
    private final FormatMarkdownWriter     fmtWriter;
    private final ContextMarkdownWriter    ctxWriter;
    private final JavaClassMarkdownWriter  javaWriter;
    private final LinkResolver             links;

    public StreamingGenerationService(
            OperationFileParser opParser, FormatFileParser fmtParser,
            ContextFileParser ctxParser, JavaClassParser javaParser,
            OperationMarkdownWriter opWriter, OpStepMarkdownWriter stepWriter,
            FormatMarkdownWriter fmtWriter, ContextMarkdownWriter ctxWriter,
            JavaClassMarkdownWriter javaWriter) {
        this(opParser, fmtParser, ctxParser, javaParser,
             opWriter, stepWriter, fmtWriter, ctxWriter, javaWriter, new LinkResolver());
    }

    public StreamingGenerationService(
            OperationFileParser opParser, FormatFileParser fmtParser,
            ContextFileParser ctxParser, JavaClassParser javaParser,
            OperationMarkdownWriter opWriter, OpStepMarkdownWriter stepWriter,
            FormatMarkdownWriter fmtWriter, ContextMarkdownWriter ctxWriter,
            JavaClassMarkdownWriter javaWriter, LinkResolver links) {
        this.opParser   = opParser;   this.fmtParser  = fmtParser;
        this.ctxParser  = ctxParser;  this.javaParser = javaParser;
        this.opWriter   = opWriter;   this.stepWriter = stepWriter;
        this.fmtWriter  = fmtWriter;  this.ctxWriter  = ctxWriter;
        this.javaWriter = javaWriter; this.links      = links;
    }

    public void generate(List<DiscoveredFile> files, Indexes x, Path vault) {
        generate(files, x, vault, new ProcessingReport());
    }

    public void generate(List<DiscoveredFile> files, Indexes x, Path vault,
                         ProcessingReport report) {
        for (var f : files) {
            switch (f.type()) {
                case XML -> {
                    if (!report.hasXmlFailure(f.path()))
                        try { generateXml(f.path(), x, vault); }
                        catch (XmlParseException e) { report.recordXmlFailure(f.path(), e); }
                }
                case JAVA -> generateJava(f.path(), x, vault);
                case INI  -> {} // already processed in IndexBuildService
            }
        }
        writeMappedFormatNotes(x, vault);
        writeChannelNotes(x, vault);
        writeChannelOperationRegistry(x, vault);
        writeUnresolved(x, vault);
    }

    // -- private helpers ------------------------------------------------------

    private void generateXml(Path xml, Indexes x, Path vault) {
        opParser.parse(xml).forEach(op -> {
            opWriter.write(op, x, links, vault);
            op.getSteps().forEach(s -> stepWriter.write(s, x, links, vault));
        });
        fmtParser.parse(xml, x).forEach(f -> fmtWriter.write(f, x, links, vault));
        ctxParser.parse(xml).forEach(c -> ctxWriter.write(c, x, links, vault));
    }

    private void generateJava(Path javaFile, Indexes x, Path vault) {
        JavaClassDef d = javaParser.parse(javaFile);
        if (d != null) javaWriter.write(d, x, links, vault);
    }

    private void writeMappedFormatNotes(Indexes x, Path vault) {
        x.tagToClass().forEach((tag, cls) -> {
            if ("opStep".equals(tag) || x.formatToSource().containsKey(tag)) return;
            FormatDef f = new FormatDef();
            f.setId(tag);
            f.setSourceFile(x.tagToSource().get(tag));
            fmtWriter.write(f, x, links, vault);
        });
    }

    /**
     * Writes one markdown note per channel under channels/.
     * Each note lists the channel's operation count, import chain,
     * tag mapping summary, and all registered operations.
     */
    private void writeChannelNotes(Indexes x, Path vault) {
        // Group operations by channel
        Map<String, List<String>> opsByChannel = new LinkedHashMap<>();
        x.channelForOperation().forEach((opName, channel) ->
            opsByChannel.computeIfAbsent(channel, k -> new ArrayList<>()).add(opName));

        opsByChannel.forEach((channel, opNames) -> {
            StringBuilder sb = new StringBuilder();
            sb.append("# Channel: ").append(channel).append("\n\n")
                .append("---\n")
                .append("entity_type: channel\n")
                .append("entity_id: ").append(channel).append("\n")
                .append("operation_count: ").append(opNames.size()).append("\n")
                .append("---\n\n");

            if (!x.dseIniImportChain().isEmpty()) {
                sb.append("## Import Chain\n");
                x.dseIniImportChain().forEach(imp -> sb.append("- ").append(imp).append("\n"));
                sb.append("\n");
            }

            sb.append("## Operations (").append(opNames.size()).append(")\n");
            opNames.stream().sorted().forEach(op -> {
                String filePath = x.channelOperationRegistry().get(op);
                sb.append("- ").append(op);
                if (filePath != null) sb.append(" -- `").append(filePath).append("`");
                sb.append("\n");
            });

            try {
                FileUtil.writeString(
                    vault.resolve("channels").resolve(channel + ".md"),
                    sb.toString());
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        });
    }

    /**
     * Writes analysis/channel-operation-registry.md -- the master index of
     * all operations across all channels, with their XML file paths.
     */
    private void writeChannelOperationRegistry(Indexes x, Path vault) {
        StringBuilder sb = new StringBuilder();
        sb.append("# Channel Operation Registry\n\n")
            .append("Master index of all operations across all channels.\n\n")
            .append("| Operation | Channel | XML File Path |\n")
            .append("|---|---|---|\n");

        x.channelForOperation().entrySet().stream()
            .sorted(Map.Entry.comparingByValue())
            .forEach(entry -> {
                String op      = entry.getKey();
                String channel = entry.getValue();
                String path    = x.channelOperationRegistry().getOrDefault(op, "");
                sb.append("| ").append(op)
                    .append(" | ").append(channel)
                    .append(" | `").append(path).append("` |\n");
            });

        try {
            FileUtil.writeString(
                vault.resolve("analysis").resolve("channel-operation-registry.md"),
                sb.toString());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    private void writeUnresolved(Indexes x, Path vault) {
        StringBuilder sb = new StringBuilder();
        sb.append("# Unresolved References\n\n## Unresolved Classes\n");
        if (x.unresolvedClassRefs().isEmpty()) sb.append("- None\n");
        else x.unresolvedClassRefs().forEach(v -> sb.append("- `").append(v).append("`\n"));

        sb.append("\n## Unresolved Formats\n");
        if (x.unresolvedFormatRefs().isEmpty()) sb.append("- None\n");
        else x.unresolvedFormatRefs().forEach(v -> sb.append("- `").append(v).append("`\n"));

        sb.append("\n## Unresolved Contexts\n");
        if (x.unresolvedContextRefs().isEmpty()) sb.append("- None\n");
        else x.unresolvedContextRefs().forEach(v -> sb.append("- `").append(v).append("`\n"));

        try {
            FileUtil.writeString(
                vault.resolve("analysis").resolve("unresolved-references.md"),
                sb.toString());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}
