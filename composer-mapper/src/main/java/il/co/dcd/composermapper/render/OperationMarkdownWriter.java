package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.OpStepDef;
import il.co.dcd.composermapper.model.OperationDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;

import java.io.IOException;
import java.nio.file.Path;

public class OperationMarkdownWriter {
  public void write(OperationDef op, Indexes x, LinkResolver links, Path vault) {
    Path out = vault.resolve("operations").resolve(op.getId() + ".md");
    StringBuilder sb = new StringBuilder();

    sb.append("# ").append(op.getId())
        .append("\n\n---\nentity_type: operation\nentity_id: ").append(op.getId())
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

    sb.append("\n## Formats\n");
    if (op.getRefFormats().isEmpty() && op.getInlineFormatIds().isEmpty()) {
      sb.append("- None\n");
    } else {
      op.getRefFormats().forEach((n, r) -> sb.append(MarkdownSupport.bullet(n + ": "
          + (x.formatToSource().containsKey(r) ? links.formatLink(r) : "unresolved " + MarkdownSupport.code(r)))));
      for (String id : op.getInlineFormatIds()) {
        sb.append(MarkdownSupport.bullet("inline: "
            + (x.formatToSource().containsKey(id) ? links.formatLink(id) : "unresolved " + MarkdownSupport.code(id))));
      }
    }

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

  private void appendNode(StringBuilder sb, String id, String label) {
    sb.append("    ").append(MarkdownSupport.mermaidNodeId(id)).append(MarkdownSupport.mermaidLabel(label)).append("\n");
  }

  private String nodeRef(String label) {
    return MarkdownSupport.mermaidNodeId(label) + MarkdownSupport.mermaidLabel(label);
  }
}
