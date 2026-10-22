package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import il.co.dcd.composermapper.util.*;
import java.util.*;

/** Resolve consuming-channel call connections without creating inherited source copies. */
public final class OperationDependencyConnections {
    private static final String COMPLEX = "com.ibm.il.dse.cc.cut.CCComplexOpStep";

    private OperationDependencyConnections() {}

    /** Give each resource occurrence one destination, independent of its consumers. */
    public static String resourcePath(SourceDefinitionIdentity source, String workspace) {
        String prefix = source.channel() == null ? "unassigned/resources"
            : "channels/" + ScopedVaultPaths.segment(source.channel()) + "/resources";
        String folder = switch (source.kind()) {
            case "format" -> "formats";
            case "context" -> "contexts";
            case "java_class" -> "classes";
            default -> throw new IllegalArgumentException("Unexpected resource: " + source.kind());
        };
        if (!source.owner().isEmpty() && source.element() != null) {
            org.w3c.dom.Node parent = source.element().getParentNode();
            while (parent instanceof org.w3c.dom.Element element) {
                if (element.getTagName().equals("CCDSEServerOperation")) {
                    prefix += "/owners/" + ScopedVaultPaths.segment(element.getAttribute("id"));
                    break;
                }
                parent = parent.getParentNode();
            }
        }
        return source.kind().equals("format") ? NestedFormatInventory.path(prefix, source)
            : ScopedVaultPaths.inventory(prefix, folder, source.relativePath(), source.selector(), source.name());
    }

    /** Return effective complex-call evidence, including explicit unresolved targets. */
    public static List<Map<String, Object>> calls(ScopedDefinitionCatalog catalog,
            SourceDefinitionIdentity operation, List<String> chain, String channel, Indexes index,
            Map<String, String> paths, String workspace) {
        List<Map<String, Object>> calls = new ArrayList<>();
        for (var step : catalog.steps(operation)) {
            if (!ChannelStepSelection.applies(XmlUtil.attr(step.element(), "onlyFor"), channel)) continue;
            String impl = XmlUtil.attr(step.element(), "implClass");
            if (impl == null || impl.isBlank()) impl = index.tagToClass().get("opStep");
            if (!COMPLEX.equals(impl)) continue;
            Map<String, Object> call = new LinkedHashMap<>();
            String name = XmlUtil.attr(step.element(), "opExecuteName");
            call.put("step", step.name()); call.put("step_note", paths.get("opsteps:" + step.selector()));
            call.put("target_name", name == null ? "" : name);
            try {
                var target = name == null || name.isBlank() ? null : catalog.resolve("operation", name, chain, null);
                if (target == null) call.put("detail", "Missing operation target in consuming channel " + channel + ": " + name);
                else if (target.channel() == null) call.put("detail", "Operation target has no source channel: " + name);
                else {
                    call.put("target_context", channel + "/" + target.name());
                    call.put("target_definition_id", target.key(workspace));
                    call.put("target_note", ScopedVaultPaths.operation(target.channel(), target.name()) + "/operation.md");
                }
            } catch (IllegalArgumentException error) { call.put("detail", error.getMessage()); }
            calls.add(call);
        }
        return calls;
    }

    /** Enumerate only referenced operations eligible in this consuming channel. */
    public static List<SourceDefinitionIdentity> targets(ScopedDefinitionCatalog catalog,
            SourceDefinitionIdentity operation, List<String> chain, String channel, Indexes index) {
        List<SourceDefinitionIdentity> targets = new ArrayList<>();
        for (var call : calls(catalog, operation, chain, channel, index, Map.of(), "")) {
            if (!call.containsKey("target_context")) continue;
            targets.add(catalog.resolve("operation", call.get("target_name").toString(), chain, null));
        }
        return targets;
    }
}
