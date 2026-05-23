package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.OpStepDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.SafePathNames;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Set;

public class OpStepMarkdownWriter {
  public void write(OpStepDef s, Indexes x, LinkResolver links, Path vault) {
    Path out = vault.resolve("opsteps").resolve(SafePathNames.document(s.getId()));
    String impl = s.getImplClass();
    if ((impl == null || impl.isBlank()) && x.tagToClass().containsKey("opStep")) {
      impl = x.tagToClass().get("opStep");
      s.setImplClass(impl);
    }

    StringBuilder sb = new StringBuilder();
    sb.append("# ").append(s.getId())
        .append("\n\n---\nentity_type: opStep\nentity_id: ").append(s.getId())
        .append("\nconversion_status: not_started\n")
        .append(MarkdownSupport.usedByList("used_by_operations", singletonSetOrEmpty(x.stepToOperation().get(s.getId()))))
        .append("source_file: ").append(s.getSourceFile())
        .append("\nsource_hash: ").append(FileUtil.sha256(s.getSourceFile()))
        .append("\n---\n\n## Implementation\n");
    if (impl == null || impl.isBlank()) {
      sb.append("- Unresolved\n");
    } else {
      sb.append(MarkdownSupport.bullet(
          x.classToSource().containsKey(impl) ? links.classLink(impl) : "Unresolved: " + MarkdownSupport.code(impl)));
    }

    sb.append("\n## Parameters\n");
    if (s.getParameters().isEmpty()) {
      sb.append("- None\n");
    } else {
      s.getParameters().forEach((k, v) -> sb.append(MarkdownSupport.bullet(k + ": " + MarkdownSupport.code(v))));
    }

    sb.append("\n## Transitions\n");
    if (s.getTransitions().isEmpty()) {
      sb.append("- None\n");
    } else {
      s.getTransitions().forEach((c, t) -> sb.append(MarkdownSupport.bullet(
          MarkdownSupport.code(c) + " -> " + (x.stepToSource().containsKey(t) ? links.stepLink(t) : "unresolved " + MarkdownSupport.code(t)))));
    }

    sb.append("\n## Parser Notes\n")
        .append("- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.\n");

    sb.append("\n## Raw Attributes\n");
    s.getRawAttributes().forEach((k, v) -> sb.append(MarkdownSupport.bullet(k + ": " + MarkdownSupport.code(v))));

    try {
      FileUtil.writeString(out, sb.toString());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  private Set<String> singletonSetOrEmpty(String value) {
    if (value == null || value.isBlank()) return Set.of();
    return Set.of(value);
  }
}
