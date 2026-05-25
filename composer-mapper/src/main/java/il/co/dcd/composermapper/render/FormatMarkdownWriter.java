package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.FormatDef;
import il.co.dcd.composermapper.model.TagNode;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.SafePathNames;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Set;

public class FormatMarkdownWriter {

    public void write(FormatDef f, Indexes x, LinkResolver links, Path vault) {
        Path out = vault.resolve("formats").resolve(SafePathNames.document(f.getId()));
        StringBuilder sb = new StringBuilder();

        sb.append("# ").append(f.getId())
            .append("\n\n---\n")
            .append("entity_type: format\n")
            .append("entity_id: ").append(f.getId()).append("\n")
            .append("conversion_status: not_started\n")
            .append("shared: ").append(isShared(f, x)).append("\n")
            .append(MarkdownSupport.usedByList("used_by_operations",
                x.formatUsedByOperations().get(f.getId())))
            .append("source_file: ").append(f.getSourceFile() != null ? f.getSourceFile() : "")
            .append("\nsource_hash: ")
                .append(f.getSourceFile() != null ? FileUtil.sha256(f.getSourceFile()) : "n/a")
            .append("\n---\n\n");

        if (f.getRootTag() != null) {
            sb.append("## Structure\n```xml\n")
                .append(tagTreeWithDecorators(f.getRootTag(), 0))
                .append("```\n\n");
        }

        appendSerializationNotes(sb, f);
        appendDatabaseLookups(sb, f);

        sb.append("\n## Referenced Tags\n");
        if (f.getReferencedXmlTags().isEmpty()) {
            sb.append("- None\n");
        } else {
            f.getReferencedXmlTags().forEach(tag ->
                sb.append(MarkdownSupport.bullet(formatLink(tag, x, links))));
        }

        sb.append("\n## Mapped Java Classes\n");
        if (f.getReferencedMappedJavaClasses().isEmpty()) {
            sb.append("- None\n");
        } else {
            f.getReferencedMappedJavaClasses().forEach(cls ->
                sb.append(MarkdownSupport.bullet(
                    x.classToSource().containsKey(cls) ? links.classLink(cls) : cls)));
        }

        sb.append("\n## Inferred External Dependencies\n");
        if (f.getInferredExternalDependencies().isEmpty()) {
            sb.append("- None\n");
        } else {
            f.getInferredExternalDependencies().forEach(
                d -> sb.append(MarkdownSupport.bullet(d)));
        }

        try {
            FileUtil.writeString(out, sb.toString());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * Renders the TagNode tree as XML-like text.
     * Decorators are shown as "decorator: <tagName .../>" indented under
     * the formatter node they follow.
     */
    private String tagTreeWithDecorators(TagNode n, int level) {
        if (n == null) return "";
        String indent = "  ".repeat(Math.max(0, level));
        StringBuilder sb = new StringBuilder();

        sb.append(indent).append("<").append(n.getTagName());
        n.getAttributes().forEach((k, v) ->
            sb.append(" ").append(k).append("=\"").append(v).append("\""));

        if (n.getChildren().isEmpty() && n.getDecorators().isEmpty()) {
            sb.append("/>\n");
        } else {
            sb.append(">\n");
            for (TagNode c : n.getChildren()) sb.append(tagTreeWithDecorators(c, level + 1));
            sb.append(indent).append("</").append(n.getTagName()).append(">\n");
        }

        // show attached decorators indented under this formatter
        for (TagNode dec : n.getDecorators()) {
            sb.append(indent).append("  ").append("decorator: <").append(dec.getTagName());
            dec.getAttributes().forEach((k, v) ->
                sb.append(" ").append(k).append("=\"").append(v).append("\""));
            sb.append("/>\n");
        }

        return sb.toString();
    }

    private void appendSerializationNotes(StringBuilder sb, FormatDef f) {
        if (f.getSerializationFlags().isEmpty()) return;
        sb.append("## Serialization Notes\n")
            .append("- This format contains CCXML serialization flags that affect the XML wire shape.\n");
        f.getSerializationFlags().forEach(
            flag -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(flag))));
        sb.append("\n");
    }

    private void appendDatabaseLookups(StringBuilder sb, FormatDef f) {
        if (f.getDatabaseLookups().isEmpty()) return;
        sb.append("## Database Lookups\n");
        sb.append("> These lookups were encoded inside the WSBCC format definition. " +
                  "In the converted service they must be moved to the service layer, " +
                  "not the serializer.\n\n");
        f.getDatabaseLookups().forEach(lookup ->
            sb.append(MarkdownSupport.bullet(
                lookup.getNodeName()
                    + ": fromTable " + codeOrMissing(lookup.getFromTable())
                    + ", fromColumn " + codeOrMissing(lookup.getFromColumn())
                    + ", keyValue " + codeOrMissing(lookup.getKeyValue()))));
        sb.append("\n");
    }

    private String codeOrMissing(String value) {
        return value == null || value.isBlank() ? "`<missing>`" : MarkdownSupport.code(value);
    }

    private String formatLink(String id, Indexes x, LinkResolver links) {
        return x.formatToSource().containsKey(id) || x.tagToClass().containsKey(id)
            ? links.formatLink(id) : id;
    }

    private boolean isShared(FormatDef f, Indexes x) {
        Set<String> ops = x.formatUsedByOperations().get(f.getId());
        return ops != null && ops.size() > 1;
    }
}
