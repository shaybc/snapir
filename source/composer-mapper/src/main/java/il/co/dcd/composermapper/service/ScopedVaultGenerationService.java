package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.index.*;
import il.co.dcd.composermapper.model.*;
import il.co.dcd.composermapper.parser.*;
import il.co.dcd.composermapper.render.*;
import il.co.dcd.composermapper.util.*;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Generate isolated channel/operation views without using the legacy global name indexes. */
public final class ScopedVaultGenerationService {
    private static final Map<String, String> FOLDERS = Map.of("operation", "operations", "opStep", "opsteps",
        "format", "formats", "context", "contexts", "java_class", "classes");
    private final List<Map<String, Object>> diagnostics = new ArrayList<>();
    private final Set<String> inventory = new HashSet<>();
    private final OperationFileParser operationParser = new OperationFileParser();
    private final FormatFileParser formatParser = new FormatFileParser();
    private final ContextFileParser contextParser = new ContextFileParser();

    /** Scoped generation requires a fresh destination; old vaults are never rearranged or deleted. */
    public void generate(Path root, Path vault, List<DiscoveredFile> files, String selectedChannel,
                         String workspace, boolean markdown, ProcessingReport report) throws IOException {
        if (workspace == null || workspace.isBlank())
            throw new IllegalArgumentException("Scoped output requires --workspace-id (stable across checkout locations)");
        if (vault.startsWith(root) || root.startsWith(vault))
            throw new IllegalArgumentException("Scoped output must be outside the source tree");
        if (Files.exists(vault)) try (var contents = Files.list(vault)) {
            if (contents.findAny().isPresent()) throw new IllegalArgumentException("Scoped output requires an empty destination: " + vault);
        }
        Files.createDirectories(vault);
        FileUtil.writeString(vault.resolve("vault-generation.json"), "{\"vault_schema_version\":2,\"complete\":false}\n");
        ScopedDefinitionCatalog catalog = new ScopedDefinitionCatalog(root, files, report);
        VaultManifestWriter manifest = new VaultManifestWriter(workspace);
        List<String> channels = selectedChannel == null ? files.stream().filter(f -> f.channel() != null
            && f.path().getFileName().toString().equalsIgnoreCase("dse.ini"))
            .map(f -> f.channel().toUpperCase(Locale.ROOT)).distinct().sorted().toList()
            : List.of(selectedChannel.toUpperCase(Locale.ROOT));
        if (channels.isEmpty()) throw new IllegalArgumentException("No channel definitions found; scoped output requires channel evidence");
        for (String channel : channels) {
            List<String> chain = new ChannelImportResolver().resolve(files, channel);
            Indexes registration = registrations(files, chain);
            Set<String> names = new TreeSet<>();
            catalog.definitions().stream().filter(d -> d.kind().equals("operation") && d.channel() != null
                && chain.contains(d.channel().toUpperCase(Locale.ROOT))).forEach(d -> names.add(d.name()));
            for (String name : names) {
                SourceDefinitionIdentity operation;
                try { operation = catalog.resolve("operation", name, chain, null); }
                catch (IllegalArgumentException e) { diagnostic(channel, name, "identity", e.getMessage()); continue; }
                writeOperation(vault, catalog, manifest, registration, chain, channel, operation, workspace, markdown);
            }
            writeChannel(vault, registration, channel, chain);
        }
        // Keep every original occurrence, including unused, shadowed and unresolved definitions.
        for (var definition : catalog.definitions()) writeInventory(vault, definition, manifest, workspace, markdown);
        if (report.hasFailures()) report.failedXmlFiles().forEach((file, error) ->
            diagnostic("", "", "source_parse", file + ": " + error));
        FileUtil.writeString(vault.resolve("analysis/entity-collisions.md"), "# Scoped resolution diagnostics\n\n"
            + String.join("\n", diagnostics.stream().map(d -> "- " + d.get("operation") + ": " + d.get("detail")).toList()) + "\n");
        if (report.hasFailures()) throw new IllegalArgumentException("Source parsing failures; scoped generation remains incomplete");
        manifest.finish(vault, diagnostics, channels);
        Files.delete(vault.resolve("vault-generation.json"));
    }

    private Indexes registrations(List<DiscoveredFile> files, List<String> chain) {
        Indexes index = Indexes.create();
        for (String channel : chain) for (var file : files)
            if (file.channel() != null && channel.equalsIgnoreCase(file.channel())
                && file.path().getFileName().toString().equalsIgnoreCase("dse.ini"))
                new IniMappingIndexer().index(file.path(), index);
        return index;
    }

    private void writeOperation(Path vault, ScopedDefinitionCatalog catalog, VaultManifestWriter manifest,
            Indexes registration, List<String> chain, String channel, SourceDefinitionIdentity operation,
            String workspace, boolean markdown) throws IOException {
        String prefix = ScopedVaultPaths.operation(channel, operation.name());
        String operationIdentity = SourceDefinitionIdentity.digest(channel, operation.key(workspace));
        Indexes index = Indexes.create();
        index.tagToClass().putAll(registration.tagToClass()); index.tagToSource().putAll(registration.tagToSource());
        index.channelForOperation().put(operation.name(), channel);
        index.operationToSource().put(operation.name(), operation.file());
        var op = operationParser.parseDefinition(operation.element(), operation.file());
        op.getSteps().removeIf(step -> !ChannelStepSelection.applies(step.getOnlyFor(), channel));
        Map<String, SourceDefinitionIdentity> selected = new LinkedHashMap<>();
        selected.put("operation:" + operation.name(), operation);
        Map<String, String> paths = new LinkedHashMap<>();
        paths.put("operations:" + operation.name(), prefix + "/operation.md");
        for (var step : catalog.steps(operation)) {
            if (!ChannelStepSelection.applies(XmlUtil.attr(step.element(), "onlyFor"), channel)) continue;
            if (index.stepToSource().putIfAbsent(step.name(), step.file()) != null)
                throw new IllegalArgumentException("Duplicate step in " + channel + "/" + operation.name() + ": " + step.name()
                    + " (source: " + step.file().toAbsolutePath().normalize() + ")");
            index.stepToOperation().put(step.name(), operation.name());
            selected.put("opStep:" + step.name(), step);
            paths.put("opsteps:" + step.name(), prefix + "/opsteps/" + ScopedVaultPaths.segment(step.name()) + ".md");
        }
        Set<String> classes = new TreeSet<>();
        op.getSteps().forEach(step -> {
            String impl = step.getImplClass();
            if (impl == null || impl.isBlank()) impl = index.tagToClass().get("opStep");
            if (impl != null && !impl.isBlank()) classes.add(impl);
        });
        Map<String, Set<String>> required = new LinkedHashMap<>();
        Set<String> formats = new TreeSet<>(op.getRefFormats().values());
        formats.addAll(op.getInlineFormatIds());
        required.put("format", formats);
        required.put("context", op.getOperationContext() == null ? Set.of() : Set.of(op.getOperationContext()));
        for (String kind : List.of("format", "context")) {
            var pending = new ArrayDeque<>(required.get(kind));
            Set<String> visited = new HashSet<>();
            while (!pending.isEmpty()) {
                String name = pending.removeFirst();
                if (name.isBlank() || name.equalsIgnoreCase("nil") || !visited.add(name)) continue;
                SourceDefinitionIdentity source;
                try { source = catalog.resolve(kind, name, chain, operation); }
                catch (IllegalArgumentException e) { diagnostic(channel, operation.name(), "resource", e.getMessage()); continue; }
                if (source == null) {
                    diagnostic(channel, operation.name(), "resource", "Missing " + kind + ": " + name);
                    continue;
                }
                selected.put(kind + ":" + name, source);
                paths.put(FOLDERS.get(kind) + ":" + name, prefix + "/" + FOLDERS.get(kind) + "/" + ScopedVaultPaths.segment(name) + ".md");
                if (kind.equals("format")) {
                    index.formatToSource().put(name, source.file());
                    var format = formatParser.parseDefinition(source.element(), source.file(), index);
                    classes.addAll(format.getReferencedMappedJavaClasses());
                    nestedFormats(source.element(), pending);
                } else {
                    index.contextToSource().put(name, source.file());
                    String parent = contextParser.parseDefinition(source.element(), source.file()).getParent();
                    if (parent != null && !parent.isBlank()) pending.add(parent);
                }
            }
        }
        // No effective classpath is inferred from folder copies or FQCN equality.
        List<Map<String, Object>> classResolution = new ArrayList<>();
        var pendingClasses = new ArrayDeque<>(classes);
        Set<String> seenClasses = new HashSet<>();
        while (!pendingClasses.isEmpty()) {
            String name = pendingClasses.removeFirst();
            if (!seenClasses.add(name)) continue;
            var candidates = catalog.candidates("java_class", name, chain, operation);
            Map<String, Object> evidence = new LinkedHashMap<>();
            evidence.put("fqcn", name); evidence.put("status", "unresolved_classpath");
            evidence.put("candidates", candidates.stream().map(d -> Map.of("definition_id", d.key(workspace),
                "source_relative_path", d.relativePath())).toList());
            classResolution.add(evidence);
            // Render a unique source candidate as evidence, without declaring it the loaded implementation.
            if (candidates.size() == 1) {
                var source = candidates.getFirst(); selected.put("java_class:" + name, source);
                index.classToSource().put(name, source.file());
                paths.put("classes:" + name, prefix + "/classes/" + ScopedVaultPaths.classPath(name) + ".md");
                var parsed = new JavaClassParser().parse(source.file());
                if (parsed != null) parsed.getImports().stream().filter(value -> !value.endsWith(".*"))
                    .filter(value -> !catalog.candidates("java_class", value, chain, operation).isEmpty()).forEach(pendingClasses::add);
            }
        }
        LinkResolver links = new LinkResolver(markdown, paths);
        new OperationMarkdownWriter().write(op, index, links, vault);
        Map<String, Object> extra = new LinkedHashMap<>();
        extra.put("references", paths); extra.put("java_resolution", classResolution);
        manifest.record(vault, operation, channel, operation.name(), operationIdentity, prefix + "/operation.md", extra);
        inventory.add(operation.key(workspace));
        for (var source : selected.values()) {
            if (source.kind().equals("operation")) continue;
            writeDefinition(source, index, links, vault);
            String path = paths.get(FOLDERS.get(source.kind()) + ":" + source.name());
            manifest.record(vault, source, channel, operation.name(), operationIdentity, path,
                Map.of("resolution_status", source.kind().equals("java_class") ? "source_candidate" : "resolved"));
            inventory.add(source.key(workspace));
        }
    }

    private void nestedFormats(org.w3c.dom.Element element, Deque<String> pending) {
        String reference = element.getAttribute("refFmt");
        if (!reference.isBlank()) pending.add(reference);
        for (var child : XmlUtil.childElements(element)) nestedFormats(child, pending);
    }

    private void writeDefinition(SourceDefinitionIdentity source, Indexes index, LinkResolver links, Path vault) {
        switch (source.kind()) {
            case "format" -> new FormatMarkdownWriter().write(formatParser.parseDefinition(source.element(), source.file(), index), index, links, vault);
            case "context" -> new ContextMarkdownWriter().write(contextParser.parseDefinition(source.element(), source.file()), index, links, vault);
            case "java_class" -> {
                var parsed = new JavaClassParser().parse(source.file());
                if (parsed == null) throw new IllegalArgumentException("Unparseable Java definition: " + source.file());
                new JavaClassMarkdownWriter().write(parsed, index, links, vault);
            }
            case "opStep" -> {
                var step = operationParser.parseStepDefinition(source.element(), index.stepToOperation().get(source.name()), source.file());
                new OpStepMarkdownWriter().write(step, index, links, vault);
            }
            default -> throw new IllegalArgumentException("Unexpected definition kind: " + source.kind());
        }
    }

    private void writeInventory(Path vault, SourceDefinitionIdentity source, VaultManifestWriter manifest,
                                 String workspace, boolean markdown) throws IOException {
        if (inventory.contains(source.key(workspace))) return;
        String prefix = source.channel() == null ? "unassigned/resources" : "channels/" + ScopedVaultPaths.segment(source.channel()) + "/resources";
        String path = ScopedVaultPaths.inventory(prefix, FOLDERS.get(source.kind()),
            source.relativePath(), source.selector(), source.name());
        if (source.kind().equals("opStep")) {
            String onlyFor = XmlUtil.attr(source.element(), "onlyFor");
            var siblings = XmlUtil.childElements((org.w3c.dom.Element) source.element().getParentNode());
            long occurrences = siblings.stream().filter(element -> element.getTagName().equals("opStep")
                && source.name().equals(XmlUtil.attr(element, "id"))).count();
            if (occurrences > 1 && onlyFor != null && !onlyFor.isBlank()) {
                int fileName = path.lastIndexOf('/');
                path = path.substring(0, fileName) + "/onlyFor/" + ScopedVaultPaths.segment(onlyFor)
                    + path.substring(fileName);
            }
        }
        // Render full original sections even when an occurrence has no selected consumer.
        Indexes index = Indexes.create();
        LinkResolver links = new LinkResolver(markdown, Map.of(FOLDERS.get(source.kind()) + ":" + source.name(), path));
        if (source.kind().equals("operation")) {
            if (source.channel() != null) index.channelForOperation().put(source.name(), source.channel());
            new OperationMarkdownWriter().write(operationParser.parseDefinition(source.element(), source.file()), index, links, vault);
        } else {
            if (source.kind().equals("opStep")) {
                var parent = (org.w3c.dom.Element) source.element().getParentNode();
                index.stepToOperation().put(source.name(), parent.getAttribute("id"));
            }
            writeDefinition(source, index, links, vault);
        }
        manifest.record(vault, source, source.channel() == null ? "" : source.channel(), "", "", path,
            Map.of("resolution_status", "inventory_only"));
    }

    private void writeChannel(Path vault, Indexes registration, String channel, List<String> chain) throws IOException {
        StringBuilder note = new StringBuilder("# Channel: " + channel + "\n\n---\nentity_type: channel\nentity_id: " + channel
            + "\nchannel: " + channel + "\n---\n\n## Import Chain\n");
        chain.forEach(c -> note.append("- ").append(c).append('\n'));
        note.append("\n## Tag Mappings\n");
        registration.tagToClass().entrySet().stream().sorted(Map.Entry.comparingByKey())
            .forEach(e -> note.append("- ").append(e.getKey()).append(" -> ").append(e.getValue()).append('\n'));
        FileUtil.writeString(vault.resolve("channels/" + ScopedVaultPaths.segment(channel) + "/channel.md"), note.toString());
    }

    private void diagnostic(String channel, String operation, String kind, String detail) {
        diagnostics.add(Map.of("operation", channel.isEmpty() ? operation : channel + "/" + operation,
            "step", "", "kind", kind, "detail", detail));
    }
}
