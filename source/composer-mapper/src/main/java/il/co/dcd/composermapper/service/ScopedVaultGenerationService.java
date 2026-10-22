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
    private final Map<String, List<String>> sourceChains = new HashMap<>();
    private final Map<String, Indexes> sourceRegistrations = new HashMap<>();
    private final OperationFileParser operationParser = new OperationFileParser();
    private final FormatFileParser formatParser = new FormatFileParser();
    private final ContextFileParser contextParser = new ContextFileParser();

    /** Scoped generation requires a fresh destination; old vaults are never rearranged or deleted. */
    public void generate(Path root, Path vault, List<DiscoveredFile> files, String selectedChannel,
                         String workspace, boolean markdown, ProcessingReport report) throws IOException {
        generate(root, vault, files, selectedChannel, workspace, markdown, report, System.nanoTime());
    }

    /** Includes entry-point discovery time in the scoped run's progress summary. */
    public void generate(Path root, Path vault, List<DiscoveredFile> files, String selectedChannel,
                         String workspace, boolean markdown, ProcessingReport report, long started) throws IOException {
        if (workspace == null || workspace.isBlank())
            throw new IllegalArgumentException("Scoped output requires --workspace-id (stable across checkout locations)");
        if (vault.startsWith(root) || root.startsWith(vault))
            throw new IllegalArgumentException("Scoped output must be outside the source tree");
        if (Files.exists(vault)) try (var contents = Files.list(vault)) {
            if (contents.findAny().isPresent()) throw new IllegalArgumentException("Scoped output requires an empty destination: " + vault);
        }
        Files.createDirectories(vault);
        FileUtil.writeString(vault.resolve("vault-generation.json"), "{\"vault_schema_version\":3,\"complete\":false}\n");
        try (MapperProgress progress = new MapperProgress(vault.resolve("composer-mapper.log"), started)) {
        try {
        progress.event("Scoped run started: root=" + root + " | source files=" + files.size()
            + " | log=" + vault.resolve("composer-mapper.log"), true);
        progress.event("Indexing source definitions", true);
        ScopedDefinitionCatalog catalog = new ScopedDefinitionCatalog(root, files, report,
            message -> progress.event(message, false));
        VaultManifestWriter manifest = new VaultManifestWriter(workspace);
        manifest.useCanonicalLayout();
        Map<String, List<String>> availableChains = sourceChains;
        Map<String, Indexes> availableRegistrations = sourceRegistrations;
        List<Map<String, Object>> connections = new ArrayList<>();
        Set<String> resolvedContexts = new HashSet<>();
        Map<String, Map<String, Object>> sourceConnections = new HashMap<>();
        List<String> channels = selectedChannel == null ? files.stream().filter(f -> f.channel() != null
            && f.path().getFileName().toString().equalsIgnoreCase("dse.ini"))
            .map(f -> f.channel().toUpperCase(Locale.ROOT)).distinct().sorted().toList()
            : List.of(selectedChannel.toUpperCase(Locale.ROOT));
        if (channels.isEmpty()) throw new IllegalArgumentException("No channel definitions found; scoped output requires channel evidence");
        progress.event("Planning channel operation totals", true);
        Map<String, List<String>> channelChains = new LinkedHashMap<>();
        Map<String, Set<String>> channelOperations = new LinkedHashMap<>();
        for (String channel : channels) {
            List<String> chain = new ChannelImportResolver().resolve(files, channel);
            channelChains.put(channel, chain);
            for (String member : chain) {
                var memberChain = availableChains.computeIfAbsent(member,
                    value -> new ChannelImportResolver().resolve(files, value));
                availableRegistrations.computeIfAbsent(member, value -> registrations(files, memberChain));
            }
            Set<String> names = new TreeSet<>();
            catalog.definitions().stream().filter(d -> d.kind().equals("operation") && d.channel() != null
                && channel.equalsIgnoreCase(d.channel())).forEach(d -> names.add(d.name()));
            channelOperations.put(channel, names);
        }
        int totalOperations = channelOperations.values().stream().mapToInt(Set::size).sum();
        int processed = 0, completed = 0, skipped = 0, channelNumber = 0;
        progress.event("Planned " + channels.size() + " channels and " + totalOperations + " operation views", true);
        for (String channel : channels) {
            channelNumber++;
            List<String> chain = channelChains.get(channel);
            Indexes registration = availableRegistrations.get(channel);
            Set<String> names = channelOperations.get(channel);
            int channelProcessed = 0;
            progress.event("Channel " + channelNumber + "/" + channels.size() + " " + channel
                + " | operation views=" + names.size(), true);
            for (String name : names) {
                processed++;
                channelProcessed++;
                progress.event("Starting operation " + processed + "/" + totalOperations + " " + channel + "/" + name
                    + " | channel operation=" + channelProcessed + "/" + names.size()
                    + " | remaining after this=" + (totalOperations - processed), channelProcessed == 1);
                SourceDefinitionIdentity operation;
                try { operation = catalog.resolve("operation", name, chain, null); }
                catch (IllegalArgumentException e) {
                    diagnostic(channel, name, "identity", e.getMessage());
                    skipped++;
                    progress.event("Skipped operation " + channel + "/" + name + ": " + e.getMessage(), true);
                    continue;
                }
                var pending = new ArrayDeque<SourceDefinitionIdentity>();
                pending.add(operation);
                while (!pending.isEmpty()) {
                    var dependency = pending.removeFirst();
                    String contextKey = channel + "/" + dependency.name();
                    if (!resolvedContexts.add(contextKey)) continue;
                    progress.event("Resolving connections " + contextKey, false);
                    String sourceChannel = dependency.channel().toUpperCase(Locale.ROOT);
                    List<String> sourceChain = availableChains.computeIfAbsent(sourceChannel,
                        value -> new ChannelImportResolver().resolve(files, value));
                    Indexes sourceRegistration = availableRegistrations.computeIfAbsent(sourceChannel,
                        value -> registrations(files, sourceChain));
                    if (!inventory.contains(dependency.key(workspace))) {
                        var sourceConnection = writeOperation(vault, catalog, manifest, sourceRegistration, sourceChain,
                            sourceChannel, dependency, workspace, markdown, true);
                        if (catalog.steps(dependency).stream().allMatch(step ->
                            ChannelStepSelection.applies(XmlUtil.attr(step.element(), "onlyFor"), sourceChannel)))
                            sourceConnections.put(dependency.key(workspace), sourceConnection);
                    }
                    var sourceConnection = sourceConnections.get(dependency.key(workspace));
                    connections.add(channel.equals(sourceChannel) && sourceConnection != null ? sourceConnection
                        : writeOperation(vault, catalog, manifest, registration, chain, channel,
                            dependency, workspace, markdown, false));
                    for (var target : OperationDependencyConnections.targets(catalog, dependency, chain, channel, registration))
                        pending.add(target);
                }
                completed++;
                progress.event("Completed operation " + channel + "/" + name + " | processed=" + processed + "/"
                    + totalOperations + " | remaining=" + (totalOperations - processed), false);
            }
            writeChannel(vault, registration, channel, chain);
            progress.event("Completed channel " + channel + " | processed operations=" + processed + "/" + totalOperations, true);
        }
        // Keep every original occurrence, including unused, shadowed and unresolved definitions.
        var inventoryDefinitions = catalog.definitions().stream().filter(d -> !inventory.contains(d.key(workspace))).toList();
        int inventoryProcessed = 0;
        progress.event("Writing unused source inventory: " + inventoryDefinitions.size() + " definitions", true);
        for (var definition : inventoryDefinitions) {
            inventoryProcessed++;
            if (inventoryProcessed == 1 || inventoryProcessed % 100 == 0 || inventoryProcessed == inventoryDefinitions.size())
                progress.event("Inventory " + inventoryProcessed + "/" + inventoryDefinitions.size() + " "
                    + definition.kind() + " " + definition.name() + " | source=" + definition.file(), false);
            writeInventory(vault, definition, manifest, workspace, markdown, catalog);
        }
        if (report.hasFailures()) report.failedXmlFiles().forEach((file, error) ->
            diagnostic("", "", "source_parse", file + ": " + error));
        FileUtil.writeString(vault.resolve("analysis/entity-collisions.md"), "# Scoped resolution diagnostics\n\n"
            + String.join("\n", diagnostics.stream().map(d -> "- " + d.get("operation") + ": " + d.get("detail")).toList()) + "\n");
        if (report.hasFailures()) throw new IllegalArgumentException("Source parsing failures; scoped generation remains incomplete");
        progress.event("Finalizing manifest and note metadata: " + manifest.noteCount() + " notes", true);
        manifest.operationContexts(connections);
        manifest.finish(vault, diagnostics, channels, message -> progress.event(message, false));
        Files.delete(vault.resolve("vault-generation.json"));
        progress.event("SUCCESS | channels=" + channels.size() + " | operation views completed=" + completed
            + " | skipped=" + skipped + " | entity notes=" + manifest.noteCount()
            + " | inventory notes=" + inventoryProcessed + " | diagnostics=" + diagnostics.size()
            + " | elapsed=" + MapperProgress.elapsed(started), true);
        } catch (IOException | RuntimeException error) {
            try { progress.event("FAILED | elapsed=" + MapperProgress.elapsed(started) + " | " + error.getMessage(), true); }
            catch (RuntimeException loggingError) { error.addSuppressed(loggingError); }
            throw error;
        }
        }
    }

    private Indexes registrations(List<DiscoveredFile> files, List<String> chain) {
        Indexes index = Indexes.create();
        for (String channel : chain) for (var file : files)
            if (file.channel() != null && channel.equalsIgnoreCase(file.channel())
                && file.path().getFileName().toString().equalsIgnoreCase("dse.ini"))
                new IniMappingIndexer().index(file.path(), index);
        return index;
    }

    private Map<String, Object> writeOperation(Path vault, ScopedDefinitionCatalog catalog, VaultManifestWriter manifest,
            Indexes registration, List<String> chain, String channel, SourceDefinitionIdentity operation,
            String workspace, boolean markdown, boolean render) throws IOException {
        String prefix = ScopedVaultPaths.operation(operation.channel(), operation.name());
        String operationIdentity = SourceDefinitionIdentity.digest(channel, operation.key(workspace));
        Indexes index = Indexes.create();
        index.tagToClass().putAll(registration.tagToClass()); index.tagToSource().putAll(registration.tagToSource());
        index.channelForOperation().put(operation.name(), channel);
        index.operationToSource().put(operation.name(), operation.file());
        var op = operationParser.parseDefinition(operation.element(), operation.file());
        op.getSteps().clear();
        var effectiveSteps = catalog.steps(operation).stream()
            .filter(step -> render || ChannelStepSelection.applies(XmlUtil.attr(step.element(), "onlyFor"), channel)).toList();
        Map<String, SourceDefinitionIdentity> selected = new LinkedHashMap<>();
        selected.put("operation:" + operation.name(), operation);
        Map<String, String> paths = new LinkedHashMap<>();
        paths.put("operations:" + operation.name(), prefix + "/operation.md");
        for (var step : effectiveSteps) {
            var parsed = operationParser.parseStepDefinition(step.element(), operation.name(), step.file());
            parsed.setOccurrenceKey(step.selector());
            op.getSteps().add(parsed);
            index.stepToSource().putIfAbsent(step.name(), step.file());
            index.stepToOperation().put(step.name(), operation.name());
            selected.put("opStep:" + step.selector(), step);
            boolean repeated = catalog.steps(operation).stream().filter(value -> ScopedVaultPaths.stepGroupKey(value.name())
                .equals(ScopedVaultPaths.stepGroupKey(step.name()))).count() > 1;
            String path = prefix + "/opsteps/" + (repeated ? "occurrences/" + (catalog.steps(operation).indexOf(step) + 1) + "/" : "")
                + ScopedVaultPaths.segment(step.name()) + ".md";
            paths.put("opsteps:" + step.selector(), path);
            if (!repeated) paths.put("opsteps:" + step.name(), path);
        }
        Set<String> classes = new TreeSet<>();
        op.getSteps().forEach(step -> {
            String impl = step.getImplClass();
            if (impl == null || impl.isBlank()) impl = index.tagToClass().get("opStep");
            if (impl != null && !impl.isBlank()) classes.add(impl);
        });
        Map<String, Set<String>> required = new LinkedHashMap<>();
        Set<String> formats = new TreeSet<>(op.getRefFormats().values());
        op.getSteps().forEach(step -> formats.addAll(step.getReturnBodySwitches().values()));
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
                paths.put(FOLDERS.get(kind) + ":" + name, OperationDependencyConnections.resourcePath(source, workspace));
                if (kind.equals("format")) {
                    index.formatToSource().put(name, source.file());
                    var format = formatParser.parseEffectiveDefinition(source.element(), source.file(), index);
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
                paths.put("classes:" + name, OperationDependencyConnections.resourcePath(source, workspace));
                var parsed = new JavaClassParser().parse(source.file());
                if (parsed != null) parsed.getImports().stream().filter(value -> !value.endsWith(".*"))
                    .filter(value -> !catalog.candidates("java_class", value, chain, operation).isEmpty()).forEach(pendingClasses::add);
            }
        }
        LinkResolver links = new LinkResolver(markdown, paths);
        links.setStepFlow(new OperationStepFlow(op.getSteps()));
        Map<String, Object> extra = new LinkedHashMap<>();
        extra.put("references", paths); extra.put("java_resolution", classResolution);
        extra.put("step_notes", op.getSteps().stream().map(step -> paths.get("opsteps:" + step.getOccurrenceKey())).toList());
        extra.put("entry_step_note", op.getSteps().isEmpty() ? "" : paths.get("opsteps:" + op.getSteps().getFirst().getOccurrenceKey()));
        extra.put("channel", channel); extra.put("operation_id", operation.name());
        extra.put("operation_identity", operationIdentity); extra.put("definition_id", operation.key(workspace));
        extra.put("note", prefix + "/operation.md");
        extra.put("calls", OperationDependencyConnections.calls(catalog, operation, chain, channel, index, paths, workspace));
        Map<String, Object> transitions = new LinkedHashMap<>();
        for (var step : op.getSteps()) {
            Map<String, String> targets = new LinkedHashMap<>();
            step.getTransitions().forEach((condition, name) -> {
                var target = links.stepFlow().target(step, name);
                if (target != null) targets.put(condition, paths.get("opsteps:" + target.getOccurrenceKey()));
            });
            transitions.put(paths.get("opsteps:" + step.getOccurrenceKey()), targets);
        }
        extra.put("transition_targets", transitions);
        if (!render) {
            // Context changes connections, never the source note or its identity.
            for (var source : selected.values()) {
                if (source.kind().equals("operation") || source.kind().equals("opStep")
                    || inventory.contains(source.key(workspace))) continue;
                String path = OperationDependencyConnections.resourcePath(source, workspace);
                manifest.reserve(source, source.channel() == null ? "" : source.channel(), "", path);
                writeCanonicalResource(source, catalog, workspace, markdown, vault);
                manifest.record(vault, source, source.channel() == null ? "" : source.channel(), "", "", path,
                    Map.of("resolution_status", source.kind().equals("java_class") ? "source_candidate" : "resolved"));
                inventory.add(source.key(workspace));
            }
            return extra;
        }
        for (var source : selected.values()) {
            if (inventory.contains(source.key(workspace))) continue;
            String path = source.kind().equals("operation") ? prefix + "/operation.md"
                : paths.get(FOLDERS.get(source.kind()) + ":"
                    + (source.kind().equals("opStep") ? source.selector() : source.name()));
            boolean owned = source.kind().equals("operation") || source.kind().equals("opStep");
            manifest.reserve(source, owned ? channel : source.channel() == null ? "" : source.channel(),
                owned ? operation.name() : "", path);
        }
        new OperationMarkdownWriter().write(op, index, links, vault);
        manifest.record(vault, operation, channel, operation.name(), operationIdentity, prefix + "/operation.md", extra);
        inventory.add(operation.key(workspace));
        for (var source : selected.values()) {
            if (inventory.contains(source.key(workspace))) continue;
            if (source.kind().equals("opStep")) writeDefinition(source, index, links, vault);
            else writeCanonicalResource(source, catalog, workspace, markdown, vault);
            String path = paths.get(FOLDERS.get(source.kind()) + ":"
                + (source.kind().equals("opStep") ? source.selector() : source.name()));
            boolean owned = source.kind().equals("opStep");
            Map<String, Object> evidence = new LinkedHashMap<>();
            evidence.put("resolution_status", source.kind().equals("java_class") ? "source_candidate" : "resolved");
            if (owned) {
                var parsed = operationParser.parseStepDefinition(source.element(), operation.name(), source.file());
                parsed.setOccurrenceKey(source.selector());
                evidence.put("step_index", links.stepFlow().position(parsed));
                evidence.put("transition_targets", transitions.get(path));
            }
            manifest.record(vault, source, owned ? channel : source.channel() == null ? "" : source.channel(),
                owned ? operation.name() : "", owned ? operationIdentity : "", path, evidence);
            inventory.add(source.key(workspace));
        }
        return extra;
    }

    /** Render a shared resource in its own source environment, not the first caller's overrides. */
    private void writeCanonicalResource(SourceDefinitionIdentity source, ScopedDefinitionCatalog catalog,
            String workspace, boolean markdown, Path vault) {
        String channel = source.channel() == null ? "" : source.channel().toUpperCase(Locale.ROOT);
        Indexes index = Indexes.create();
        LinkResolver links = CanonicalResourceLinks.resolve(catalog, source,
            sourceChains.getOrDefault(channel, List.of()), sourceRegistrations.getOrDefault(channel, Indexes.create()),
            index, workspace, markdown);
        writeDefinition(source, index, links, vault);
    }

    private void nestedFormats(org.w3c.dom.Element element, Deque<String> pending) {
        String reference = element.getAttribute("refFmt");
        if (!reference.isBlank()) pending.add(reference);
        if (element.getTagName().equalsIgnoreCase("refFmt") || element.getTagName().equalsIgnoreCase("refFormat")) {
            String target = XmlUtil.attrIgnoreCase(element, "refid");
            if (target != null && !target.isBlank()) pending.add(target);
        }
        for (var child : il.co.dcd.composermapper.util.FormatCollectionPolicy.children(element, child -> false))
            nestedFormats(child, pending);
    }

    private void writeDefinition(SourceDefinitionIdentity source, Indexes index, LinkResolver links, Path vault) {
        switch (source.kind()) {
            case "format" -> new FormatMarkdownWriter().write(formatParser.parseEffectiveDefinition(source.element(), source.file(), index), index, links, vault);
            case "context" -> new ContextMarkdownWriter().write(contextParser.parseDefinition(source.element(), source.file()), index, links, vault);
            case "java_class" -> {
                var parsed = new JavaClassParser().parse(source.file());
                if (parsed == null) throw new IllegalArgumentException("Unparseable Java definition: " + source.file());
                new JavaClassMarkdownWriter().write(parsed, index, links, vault);
            }
            case "opStep" -> {
                var step = operationParser.parseStepDefinition(source.element(), index.stepToOperation().get(source.name()), source.file());
                if (links.stepFlow() != null) step.setOccurrenceKey(source.selector());
                new OpStepMarkdownWriter().write(step, index, links, vault);
            }
            default -> throw new IllegalArgumentException("Unexpected definition kind: " + source.kind());
        }
    }

    private void writeInventory(Path vault, SourceDefinitionIdentity source, VaultManifestWriter manifest,
                                 String workspace, boolean markdown, ScopedDefinitionCatalog catalog) throws IOException {
        if (inventory.contains(source.key(workspace))) return;
        String prefix = source.channel() == null ? "unassigned/resources" : "channels/" + ScopedVaultPaths.segment(source.channel()) + "/resources";
        String path = ScopedVaultPaths.inventory(prefix, FOLDERS.get(source.kind()),
            source.relativePath(), source.selector(), source.name());
        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("resolution_status", "inventory_only");
        if (source.kind().equals("format")) {
            path = NestedFormatInventory.path(prefix, source);
            var parent = NestedFormatInventory.parent(source);
            if (parent != null) {
                evidence.put("parent_definition_id", parent.key(workspace));
                evidence.put("parent_source_selector", parent.selector());
                evidence.put("nested_format_index", NestedFormatInventory.ordinal(source, parent));
            }
        }
        if (!source.kind().equals("operation") && !source.kind().equals("opStep"))
            path = OperationDependencyConnections.resourcePath(source, workspace);
        if (source.kind().equals("opStep")) {
            String onlyFor = XmlUtil.attr(source.element(), "onlyFor");
            var siblings = XmlUtil.childElements((org.w3c.dom.Element) source.element().getParentNode());
            long occurrences = siblings.stream().filter(element -> element.getTagName().equals("opStep")
                && ScopedVaultPaths.stepGroupKey(source.name()).equals(
                    ScopedVaultPaths.stepGroupKey(XmlUtil.attr(element, "id")))).count();
            if (occurrences > 1 && onlyFor != null && !onlyFor.isBlank()) {
                int fileName = path.lastIndexOf('/');
                path = path.substring(0, fileName) + "/onlyFor/" + ScopedVaultPaths.segment(onlyFor)
                    + path.substring(fileName);
            }
            if (occurrences > 1) {
                int fileName = path.lastIndexOf('/');
                String ordinal = source.selector().substring(source.selector().lastIndexOf('[') + 1,
                    source.selector().length() - 1);
                var parent = (org.w3c.dom.Element) source.element().getParentNode();
                path = path.substring(0, fileName) + "/occurrences/" + ScopedVaultPaths.segment(parent.getAttribute("id"))
                    + "/" + ordinal + path.substring(fileName);
            }
        }
        manifest.reserve(source, source.channel() == null ? "" : source.channel(), "", path);
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
            if (source.kind().equals("opStep")) writeDefinition(source, index, links, vault);
            else writeCanonicalResource(source, catalog, workspace, markdown, vault);
        }
        manifest.record(vault, source, source.channel() == null ? "" : source.channel(), "", "", path,
            evidence);
        inventory.add(source.key(workspace));
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
