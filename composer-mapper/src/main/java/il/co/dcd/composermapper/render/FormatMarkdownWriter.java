package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.FormatDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Set;

public class FormatMarkdownWriter {
  public void write(FormatDef f, Indexes x, LinkResolver links, Path vault) {
    Path out = vault.resolve("formats").resolve(f.getId() + ".md");
    StringBuilder sb = new StringBuilder();

    sb.append("# ").append(f.getId())
        .append("\n\n---\nentity_type: format\nentity_id: ").append(f.getId())
        .append("\nconversion_status: not_started")
        .append("\nshared: ").append(isShared(f, x))
        .append("\nsource_file: ").append(f.getSourceFile())
        .append("\nsource_hash: ").append(FileUtil.sha256(f.getSourceFile()))
        .append("\n---\n\n");

    appendSerializationNotes(sb, f);
    appendDatabaseLookups(sb, f);

    sb.append("## Structure\n");
    if (f.getRootTag() == null) {
      sb.append("- None\n\n");
    } else {
      sb.append("```xml\n")
          .append(MarkdownSupport.tagTree(f.getRootTag(), 0))
          .append("```\n\n");
    }

    sb.append("## Referenced Formats\n");
    if (f.getReferencedXmlTags().isEmpty()) {
      sb.append("- None\n");
    } else {
      f.getReferencedXmlTags().forEach(t -> sb.append(MarkdownSupport.bullet(formatLink(t, x, links))));
    }

    sb.append("\n## Implementation Class\n");
    String implementationClass = x.tagToClass().get(f.getId());
    if (implementationClass == null || implementationClass.isBlank()) {
      sb.append("- None\n");
    } else {
      sb.append(MarkdownSupport.bullet(
          x.classToSource().containsKey(implementationClass)
              ? links.classLink(implementationClass)
              : "Unresolved: " + MarkdownSupport.code(implementationClass)));
    }

    sb.append("\n## Inferred External Dependencies\n");
    if (f.getInferredExternalDependencies().isEmpty()) {
      sb.append("- None\n");
    } else {
      f.getInferredExternalDependencies().forEach(d -> sb.append(MarkdownSupport.bullet(d)));
    }

    try {
      FileUtil.writeString(out, sb.toString());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  private void appendSerializationNotes(StringBuilder sb, FormatDef f) {
    if (f.getSerializationFlags().isEmpty()) return;

    sb.append("## Serialization Notes\n")
        .append("- This format contains CCXML serialization flags that can change the XML wire shape.\n");
    f.getSerializationFlags().forEach(flag -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(flag))));
    sb.append("\n");
  }

  private void appendDatabaseLookups(StringBuilder sb, FormatDef f) {
    if (f.getDatabaseLookups().isEmpty()) return;

    sb.append("## Database Lookups\n");
    f.getDatabaseLookups().forEach(lookup -> sb.append(MarkdownSupport.bullet(
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
    return x.formatToSource().containsKey(id) || x.tagToClass().containsKey(id) ? links.formatLink(id) : id;
  }

  private boolean isShared(FormatDef f, Indexes x) {
    Set<String> ops = x.formatUsedByOperations().get(f.getId());
    return ops != null && ops.size() > 1;
  }
}
