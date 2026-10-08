package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.OpStepDef;
import il.co.dcd.composermapper.model.OperationDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.SafePathNames;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;

public class OperationMarkdownWriter {

    public void write(OperationDef op, Indexes x, LinkResolver links, Path vault) {
        Path out = vault.resolve("operations").resolve(SafePathNames.document(op.getId()));
        String channel = x.channelForOperation().get(op.getId());
        StringBuilder sb = new StringBuilder();

        sb.append("# ").append(op.getId())
            .append("\n\n---\n")
            .append("entity_type: operation\n")
            .append("entity_id: ").append(op.getId()).append("\n")
            .append("conversion_status: not_started\n")
            .append("entry_step: ").append(entryStep(op)).append("\n");

        // channel as plain string -- not a link
        if (channel != null && !channel.isBlank())
            sb.append("channel: ").append(channel).append("\n");
        if (op.getHostKey() != null && !op.getHostKey().isBlank())
            sb.append("host_key: ").append(op.getHostKey()).append("\n");

        sb.append("source_file: ").append(op.getSourceFile())
            .append("\nsource_hash: ").append(FileUtil.sha256(op.getSourceFile()))
            .append("\n---\n\n");

        // context
        sb.append("## Context\n");
        if (op.getOperationContext() == null || op.getOperationContext().isBlank()) {
            sb.append("- None\n");
        } else if (x.contextToSource().containsKey(op.getOperationContext())) {
            sb.append(MarkdownSupport.bullet(links.contextLink(op.getOperationContext())));
        } else {
            sb.append(MarkdownSupport.bullet("Unresolved: " +
                MarkdownSupport.code(op.getOperationContext())));
        }

        appendSharedComponents(sb, op, x, links);
        appendOperationAttributes(sb, op);

        // steps
        sb.append("\n## Steps\n");
        if (op.getSteps().isEmpty()) {
            sb.append("- None\n");
        } else {
            for (OpStepDef s : op.getSteps()) {
                String bullet = links.stepLink(s.getId());
                if (s.getOnlyFor() != null && !s.getOnlyFor().isBlank())
                    bullet += " *(onlyFor: " + s.getOnlyFor() + ")*";
                sb.append(MarkdownSupport.bullet(bullet));
            }
        }

        appendFormats(sb, op, x, links);

        // java dependencies
        sb.append("\n## Java Dependencies\n");
        boolean any = false;
        for (OpStepDef s : op.getSteps()) {
            String impl = s.getImplClass();
            if (impl != null && !impl.isBlank()) {
                any = true;
                sb.append(MarkdownSupport.bullet(
                    x.classToSource().containsKey(impl)
                        ? links.classLink(impl)
                        : "Unresolved: " + MarkdownSupport.code(impl)));
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

    // -- private helpers ------------------------------------------------------

    private void appendOperationAttributes(StringBuilder sb, OperationDef op) {
        boolean hasAttrs = anyNonBlank(op.getOperationFields(), op.getWriteToLog(),
                                       op.getWriteToOfecStat(), op.getIsSelectiveJournalising());
        boolean hasIni   = !op.getIniValues().isEmpty();

        if (!hasAttrs && !hasIni) return;

        if (hasAttrs) {
            sb.append("\n## Operation Attributes\n");
            appendAttr(sb, "operationFields",         op.getOperationFields());
            appendAttr(sb, "writeToLog",              op.getWriteToLog());
            appendAttr(sb, "writeToOfecStat",         op.getWriteToOfecStat());
            appendAttr(sb, "isSelectiveJournalising", op.getIsSelectiveJournalising());
        }

        if (hasIni) {
            sb.append("\n## Initial Values (iniValue)\n");
            op.getIniValues().forEach(v ->
                sb.append(MarkdownSupport.bullet(MarkdownSupport.code(v))));
        }
    }

    private void appendAttr(StringBuilder sb, String name, String value) {
        if (value != null && !value.isBlank())
            sb.append(MarkdownSupport.bullet(name + ": " + MarkdownSupport.code(value)));
    }

    private boolean anyNonBlank(String... values) {
        for (String v : values) if (v != null && !v.isBlank()) return true;
        return false;
    }

    private void appendSharedComponents(StringBuilder sb, OperationDef op,
                                         Indexes x, LinkResolver links) {
        Map<String, String> shared = new LinkedHashMap<>();

        String context = op.getOperationContext();
        if (context != null && !context.isBlank() && isSharedContext(context, x))
            shared.put("context " + context, links.contextLink(context));

        for (String formatId : op.getRefFormats().values()) {
            Set<String> ops = x.formatUsedByOperations().get(formatId);
            if (ops != null && ops.size() > 1)
                shared.put("format " + formatId, formatRef(formatId, x, links));
        }

        for (OpStepDef step : op.getSteps()) {
            String impl  = step.getImplClass();
            Set<String> steps = x.classUsedBySteps().get(impl);
            if (impl != null && !impl.isBlank() && steps != null && steps.size() > 1)
                shared.put("implClass " + impl,
                    x.classToSource().containsKey(impl)
                        ? links.classLink(impl)
                        : "Unresolved: " + MarkdownSupport.code(impl));
        }

        sb.append("\n## Shared Components\n");
        if (shared.isEmpty()) { sb.append("- None\n"); return; }
        sb.append(MarkdownSupport.bullet(
            shared.size() + " shared component" + (shared.size() == 1 ? "" : "s")));
        shared.forEach((label, link) ->
            sb.append(MarkdownSupport.bullet(label + ": " + link)));
    }

    private boolean isSharedContext(String context, Indexes x) {
        Set<String> ops = x.contextUsedByOperations().get(context);
        return ops != null && ops.size() > 1;
    }

    private void appendFlowDiagram(StringBuilder sb, OperationDef op) {
        sb.append("\n## Flow Diagram\n```mermaid\ngraph TD\n");
        if (op.getSteps().isEmpty()) {
            appendNode(sb, "EMPTY", "No steps");
        } else {
            for (OpStepDef s : op.getSteps()) {
                String from  = nodeRef(s.getId());
                // annotate channel-restricted steps
                String label = s.getOnlyFor() != null && !s.getOnlyFor().isBlank()
                    ? s.getId() + "\\n[" + s.getOnlyFor() + " only]"
                    : s.getId();
                String fromAnnotated = MarkdownSupport.mermaidNodeId(s.getId())
                    + MarkdownSupport.mermaidLabel(label);

                if (s.getTransitions().isEmpty()) {
                    sb.append("    ").append(fromAnnotated)
                        .append(" --> ").append(nodeRef("END")).append("\n");
                } else {
                    s.getTransitions().forEach((c, t) ->
                        sb.append("    ").append(fromAnnotated)
                            .append(" -->")
                            .append(MarkdownSupport.mermaidEdgeLabel(c))
                            .append(" ").append(nodeRef(t)).append("\n"));
                }

                // show return body switches as dashed edges to error format
                s.getReturnBodySwitches().forEach((rc, fmt) ->
                    sb.append("    ").append(fromAnnotated)
                        .append(" -.->")
                        .append(MarkdownSupport.mermaidEdgeLabel("RC" + rc + "->body"))
                        .append(" ").append(nodeRef(fmt)).append("\n"));
            }
        }
        sb.append("```\n");
    }

    private String entryStep(OperationDef op) {
        return op.getSteps().isEmpty() ? "" : op.getSteps().get(0).getId();
    }

    private void appendFormats(StringBuilder sb, OperationDef op, Indexes x, LinkResolver links) {
        appendNamedFormat(sb, "Request Format", refFormat(op, "csRequestFormat"), x, links);
        appendNamedFormat(sb, "Reply Format",   refFormat(op, "csReplyFormat"),   x, links);

        sb.append("\n## Other Formats\n");
        boolean any = false;
        for (var entry : op.getRefFormats().entrySet()) {
            if (isNamedFormat(entry.getKey(), "csRequestFormat")
                    || isNamedFormat(entry.getKey(), "csReplyFormat")) continue;
            any = true;
            sb.append(MarkdownSupport.bullet(
                entry.getKey() + ": " + formatRef(entry.getValue(), x, links)));
        }
        for (String id : op.getInlineFormatIds()) {
            any = true;
            sb.append(MarkdownSupport.bullet("inline: " + formatRef(id, x, links)));
        }
        if (!any) sb.append("- None\n");
    }

    private String refFormat(OperationDef op, String name) {
        String exact = op.getRefFormats().get(name);
        if (exact != null) return exact;
        for (var entry : op.getRefFormats().entrySet()) {
            if (isNamedFormat(entry.getKey(), name)) return entry.getValue();
        }
        return null;
    }

    private boolean isNamedFormat(String actual, String expected) {
        return actual != null && actual.equalsIgnoreCase(expected);
    }

    private void appendNamedFormat(StringBuilder sb, String heading, String formatId,
                                    Indexes x, LinkResolver links) {
        sb.append("\n## ").append(heading).append("\n");
        if (formatId == null || formatId.isBlank()) { sb.append("- None\n"); return; }
        sb.append(MarkdownSupport.bullet(formatRef(formatId, x, links)));
    }

    private String formatRef(String formatId, Indexes x, LinkResolver links) {
        return x.formatToSource().containsKey(formatId)
            ? links.formatLink(formatId)
            : "unresolved " + MarkdownSupport.code(formatId);
    }

    private void appendNode(StringBuilder sb, String id, String label) {
        sb.append("    ").append(MarkdownSupport.mermaidNodeId(id))
            .append(MarkdownSupport.mermaidLabel(label)).append("\n");
    }

    private String nodeRef(String label) {
        return MarkdownSupport.mermaidNodeId(label) + MarkdownSupport.mermaidLabel(label);
    }
}
