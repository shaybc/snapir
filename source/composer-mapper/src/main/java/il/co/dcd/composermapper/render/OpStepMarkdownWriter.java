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
        if ((impl == null || impl.isBlank()) && x.tagToClass().containsKey("opStep"))
            impl = x.tagToClass().get("opStep");
        if (impl != null) s.setImplClass(impl);

        StringBuilder sb = new StringBuilder();
        sb.append("# ").append(s.getId())
            .append("\n\n---\n")
            .append("entity_type: opStep\n")
            .append("entity_id: ").append(s.getId()).append("\n")
            .append("conversion_status: not_started\n");

        // onlyFor as plain string in frontmatter (no link -- it's a channel name, not an entity)
        if (s.getOnlyFor() != null && !s.getOnlyFor().isBlank())
            sb.append("onlyFor: ").append(s.getOnlyFor()).append("\n");

        sb.append(MarkdownSupport.usedByList("used_by_operations",
                singletonSetOrEmpty(x.stepToOperation().get(s.getId()))))
            .append("source_file: ").append(s.getSourceFile())
            .append("\nsource_hash: ").append(FileUtil.sha256(s.getSourceFile()))
            .append("\n---\n\n");

        // channel restriction callout
        if (s.getOnlyFor() != null && !s.getOnlyFor().isBlank()) {
            sb.append("> **Channel restriction:** this step only runs on channel(s): `")
                .append(s.getOnlyFor())
                .append("`. It is absent from the generated code for all other channels.\n\n");
        }

        sb.append("## Implementation\n");
        if (impl == null || impl.isBlank()) {
            sb.append("- Unresolved\n");
        } else {
            sb.append(MarkdownSupport.bullet(
                x.classToSource().containsKey(impl)
                    ? links.classLink(impl)
                    : "Unresolved: " + MarkdownSupport.code(impl)));
        }

        sb.append("\n## Parameters\n");
        if (s.getParameters().isEmpty()) sb.append("- None\n");
        else s.getParameters().forEach((k, v) ->
            sb.append(MarkdownSupport.bullet(k + ": " + MarkdownSupport.code(v))));

        sb.append("\n## Transitions\n");
        if (s.getTransitions().isEmpty()) sb.append("- None\n");
        else s.getTransitions().forEach((c, t) ->
            sb.append(MarkdownSupport.bullet(
                MarkdownSupport.code(c) + " -> " + (x.stepToSource().containsKey(t)
                    ? links.stepLink(t) : "unresolved " + MarkdownSupport.code(t)))));

        if (!s.getReturnBodySwitches().isEmpty()) {
            sb.append("\n## Return Body Switches\n");
            sb.append("- When these return codes occur, the reply format body is switched " +
                      "to the named error format before the response is built.\n");
            s.getReturnBodySwitches().forEach((rc, fmt) ->
                sb.append(MarkdownSupport.bullet(
                    "RC " + MarkdownSupport.code(rc) + " -> switch reply body to " +
                    MarkdownSupport.code(fmt))));
        }

        sb.append("\n## Parser Notes\n")
            .append("- Transition attributes are detected with the `on*Do` naming pattern. "
                + "Verify this covers all transition names used in the source WSBCC codebase "
                + "before relying on `Parameters` as transition-free.\n");

        sb.append("\n## Raw Attributes\n");
        s.getRawAttributes().forEach((k, v) ->
            sb.append(MarkdownSupport.bullet(k + ": " + MarkdownSupport.code(v))));

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
