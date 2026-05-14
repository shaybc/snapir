package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.model.ContextDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;

import java.io.IOException;
import java.nio.file.Path;

public class ContextMarkdownWriter {
  public void write(ContextDef c, LinkResolver links, Path vault) {
    Path out = vault.resolve("contexts").resolve(c.getId() + ".md");
    StringBuilder sb = new StringBuilder();

    sb.append("# ").append(c.getId())
        .append("\n\n---\nentity_type: context\nentity_id: ").append(c.getId())
        .append("\nconversion_status: not_started")
        .append("\nsource_file: ").append(c.getSourceFile())
        .append("\nsource_hash: ").append(FileUtil.sha256(c.getSourceFile()))
        .append("\n---\n\n## Details\n");

    sb.append(MarkdownSupport.bullet("parent: " + parentLink(c.getParent(), links)));
    sb.append(MarkdownSupport.bullet("type: " + MarkdownSupport.code(String.valueOf(c.getType()))));

    sb.append("\n## Raw Attributes\n");
    c.getRawAttributes().forEach((k, v) -> sb.append(MarkdownSupport.bullet(k + ": " + MarkdownSupport.code(v))));

    try {
      FileUtil.writeString(out, sb.toString());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  private String parentLink(String parent, LinkResolver links) {
    if (parent == null || parent.isBlank() || "nil".equalsIgnoreCase(parent)) {
      return MarkdownSupport.code(String.valueOf(parent));
    }
    return links.contextLink(parent);
  }
}
