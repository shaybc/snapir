package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.OpStepDef;
import il.co.dcd.composermapper.model.OperationDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.SafePathNames;

import java.io.IOException;
import java.nio.file.Path;

public class OperationMarkdownWriter {
  public void write(OperationDef op, Indexes x, LinkResolver links, Path vault) {
    Path out = vault.resolve("operations").resolve(SafePathNames.document(op.getId()));
    StringBuilder sb = new StringBuilder();

    sb.append("# ").append(op.getId())
        .append("\n\n---\nentity_type: operation\nentity_id: ").append(op.getId())
        .append("\nconversion_status: not_started")
        .append("\nentry_step: ").append(entryStep(op))
        .append("\nsource_file: ").append(op.getSourceFile())
        .append("\nsource_hash: ").append(FileUtil.sha256(op.getSourceFile()))
        .append("\n---\n\n## Context\n");

    if (op.getOperationContext() == null || op.getOperationContext().isBlank()) {
      sb.append("- None\n");
    } else if (x.contextToSource().containsKey(op.getOperationContext())) {
      sb.append(MarkdownSupport.bullet(links.contextLink(op.getOperationContext())));
    } else {
      sb.append(MarkdownSupport.bullet("Unresolved: " + MarkdownSupport.code(op.getOperationContext())));
    }

    sb.append("\n## Steps\n");
    if (op.getSteps().isEmpty()) {
      sb.append("- None\n");
    } else {
      for (OpStepDef s : op.getSteps()) {
        sb.append(MarkdownSupport.bullet(links.stepLink(s.getId())));
      }
    }

    appendFormats(sb, op, x, links);

    sb.append("\n## Java Dependencies\n");
    boolean any = false;
    for (OpStepDef s : op.getSteps()) {
      String impl = s.getImplClass();
      if (impl != null && !impl.isBlank()) {
        any = true;
        sb.append(MarkdownSupport.bullet(
            x.classToSource().containsKey(impl) ? links.classLink(impl) : "Unresolved: " + MarkdownSupport.code(impl)));
      }
    }
    if (!any) sb.append("- None\n");

    appendFlowDiagram(sb, op);

    try {
      FileUtil.writeString(out, sb.toString());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  private void appendFlowDiagram(StringBuilder sb, OperationDef op) {
    sb.append("\n## Flow Diagram\n```mermaid\ngraph TD\n");
    if (op.getSteps().isEmpty()) {
      appendNode(sb, "EMPTY", "No steps");
    } else {
      for (OpStepDef s : op.getSteps()) {
        String from = nodeRef(s.getId());
        if (s.getTransitions().isEmpty()) {
          sb.append("    ").append(from).append(" --> ").append(nodeRef("END")).append("\n");
        } else {
          s.getTransitions().forEach((c, t) -> sb.append("    ")
              .append(from)
              .append(" -->")
              .append(MarkdownSupport.mermaidEdgeLabel(c))
              .append(" ")
              .append(nodeRef(t))
              .append("\n"));
        }
      }
    }
    sb.append("```\n");
  }

  private String entryStep(OperationDef op) {
    return op.getSteps().isEmpty() ? "" : op.getSteps().get(0).getId();
  }

  private void appendFormats(StringBuilder sb, OperationDef op, Indexes x, LinkResolver links) {
    appendNamedFormat(sb, "Request Format", op.getRefFormats().get("csRequestFormat"), x, links);
    appendNamedFormat(sb, "Reply Format", op.getRefFormats().get("csReplyFormat"), x, links);

    sb.append("\n## Other Formats\n");
    boolean any = false;
    for (var entry : op.getRefFormats().entrySet()) {
      if ("csRequestFormat".equals(entry.getKey()) || "csReplyFormat".equals(entry.getKey())) continue;
      any = true;
      sb.append(MarkdownSupport.bullet(entry.getKey() + ": " + formatRef(entry.getValue(), x, links)));
    }
    for (String id : op.getInlineFormatIds()) {
      any = true;
      sb.append(MarkdownSupport.bullet("inline: " + formatRef(id, x, links)));
    }
    if (!any) sb.append("- None\n");
  }

  private void appendNamedFormat(StringBuilder sb, String heading, String formatId, Indexes x, LinkResolver links) {
    sb.append("\n## ").append(heading).append("\n");
    if (formatId == null || formatId.isBlank()) {
      sb.append("- None\n");
      return;
    }
    sb.append(MarkdownSupport.bullet(formatRef(formatId, x, links)));
  }

  private String formatRef(String formatId, Indexes x, LinkResolver links) {
    return x.formatToSource().containsKey(formatId) ? links.formatLink(formatId) : "unresolved " + MarkdownSupport.code(formatId);
  }

  private void appendNode(StringBuilder sb, String id, String label) {
    sb.append("    ").append(MarkdownSupport.mermaidNodeId(id)).append(MarkdownSupport.mermaidLabel(label)).append("\n");
  }

  private String nodeRef(String label) {
    return MarkdownSupport.mermaidNodeId(label) + MarkdownSupport.mermaidLabel(label);
  }
}
