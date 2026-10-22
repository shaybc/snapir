package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.JsonOutput;
import java.nio.file.*;
import java.io.IOException;
import java.util.*;

/** Publish the complete scoped inventory only after all generated notes are available. */
public final class VaultManifestWriter {
    private final String workspace;
    private int schemaVersion = 2;
    private List<Map<String, Object>> operationContexts = List.of();
    private final List<Map<String, Object>> entries = new ArrayList<>();
    private final Set<String> paths = new HashSet<>();
    private final Map<String, String> reservations = new HashMap<>();

    public VaultManifestWriter(String workspace) { this.workspace = workspace; }

    /** Opt into shared source notes; legacy manifest callers keep schema two. */
    public void useCanonicalLayout() { schemaVersion = 3; }

    /** Attach reachable consuming-channel connections without adding entity notes. */
    public void operationContexts(List<Map<String, Object>> contexts) { operationContexts = List.copyOf(contexts); }

    /** Reserves a destination before rendering so a later occurrence cannot overwrite it. */
    public void reserve(SourceDefinitionIdentity source, String channel, String operation, String path) {
        String owner = describe(source, channel, operation);
        String previous = reservations.putIfAbsent(path.toLowerCase(Locale.ROOT), owner);
        if (previous != null) throw new IllegalArgumentException("Duplicate note path before writing: " + path
            + " | first: " + previous + " | conflicting: " + owner);
    }

    private String describe(SourceDefinitionIdentity source, String channel, String operation) {
        return source.kind() + " " + source.name() + " | channel=" + channel + " | operation=" + operation
            + " | source=" + source.file().toAbsolutePath().normalize() + "#" + source.selector();
    }

    public Map<String, Object> record(Path vault, SourceDefinitionIdentity source, String channel,
            String operation, String operationIdentity, String path, Map<String, Object> extra) throws IOException {
        if (!describe(source, channel, operation).equals(reservations.get(path.toLowerCase(Locale.ROOT))))
            throw new IllegalArgumentException("Note destination was not reserved for this occurrence: " + path);
        if (!paths.add(path.toLowerCase(Locale.ROOT))) throw new IllegalArgumentException("Duplicate note path: " + path);
        String definition = source.key(workspace);
        String usage = SourceDefinitionIdentity.digest(channel, operationIdentity, definition, path);
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("kind", source.kind()); entry.put("entity_id", source.name());
        entry.put("definition_id", definition); entry.put("usage_id", usage);
        entry.put("channel", channel); entry.put("operation_id", operation);
        entry.put("operation_identity", operationIdentity); entry.put("note", path);
        entry.put("definition_channel", source.channel());
        entry.put("source_relative_path", source.relativePath()); entry.put("source_selector", source.selector());
        entry.put("source_hash", source.revision()); entry.putAll(extra);
        Path note = vault.resolve(path);
        String content = Files.readString(note);
        int frontmatter = content.indexOf("---\n");
        if (frontmatter < 0) throw new IllegalArgumentException("Missing note frontmatter: " + path);
        String metadata = "vault_schema_version: " + schemaVersion + "\nqualified_entity_id: " + definition + "\nusage_id: " + usage
            + "\noperation_identity: " + operationIdentity + "\nsource_workspace_id: " + workspace
            + "\nsource_relative_path: " + JsonOutput.encode(source.relativePath())
            + "\nsource_selector: " + JsonOutput.encode(source.selector()) + "\n";
        if (!source.kind().equals("operation")) metadata += "channel: " + JsonOutput.encode(channel) + "\n";
        FileUtil.writeString(note, content.substring(0, frontmatter + 4) + metadata + content.substring(frontmatter + 4));
        entry.put("note_hash", FileUtil.sha256(note));
        entries.add(entry);
        return entry;
    }

    public void finish(Path vault, List<Map<String, Object>> diagnostics, List<String> channels) throws IOException {
        finish(vault, diagnostics, channels, message -> {});
    }

    /** Finalizes the same manifest with progress callbacks for long metadata passes. */
    public void finish(Path vault, List<Map<String, Object>> diagnostics, List<String> channels,
                       java.util.function.Consumer<String> progress) throws IOException {
        Map<String, Set<String>> consumersByDefinition = new HashMap<>();
        for (var entry : entries) {
            String operation = entry.get("operation_identity").toString();
            if (schemaVersion != 3 && !operation.isBlank()) consumersByDefinition.computeIfAbsent(entry.get("definition_id").toString(),
                ignored -> new TreeSet<>()).add(operation);
        }
        Map<String, String> definitionsByNote = new HashMap<>();
        for (var entry : entries) definitionsByNote.put(entry.get("note").toString(), entry.get("definition_id").toString());
        for (var context : operationContexts) {
            @SuppressWarnings("unchecked")
            Map<String, String> references = (Map<String, String>) context.get("references");
            for (String note : references.values()) {
                String definition = definitionsByNote.get(note);
                if (definition == null) throw new IllegalArgumentException("Missing canonical dependency note: " + note);
                consumersByDefinition.computeIfAbsent(definition, ignored -> new TreeSet<>())
                    .add(context.get("operation_identity").toString());
            }
        }
        int processed = 0;
        for (var entry : entries) {
            processed++;
            if (processed == 1 || processed % 100 == 0 || processed == entries.size())
                progress.accept("Finalizing note " + processed + "/" + entries.size() + ": " + entry.get("note"));
            var consumers = consumersByDefinition.getOrDefault(entry.get("definition_id").toString(), Set.of()).stream().toList();
            entry.put("qualified_consumers", consumers);
            if (entry.get("kind").equals("format") || entry.get("kind").equals("context")) {
                Path note = vault.resolve(entry.get("note").toString());
                String content = Files.readString(note);
                if (content.contains("\nshared: ")) content = content.replaceFirst("\nshared: (true|false)", "\nshared: " + (consumers.size() > 1));
                else content = content.replaceFirst("\nconversion_status:", "\nshared: " + (consumers.size() > 1) + "\nconversion_status:");
                FileUtil.writeString(note, content);
                entry.put("note_hash", FileUtil.sha256(note));
            }
        }
        Map<String, Object> manifest = new LinkedHashMap<>();
        manifest.put("vault_schema_version", schemaVersion); manifest.put("identity_version", 1);
        manifest.put("producer", "composer-mapper"); manifest.put("complete", true);
        manifest.put("workspace_id", workspace); manifest.put("channels", channels);
        manifest.put("entities", entries);
        if (schemaVersion == 3) manifest.put("operation_contexts", operationContexts);
        manifest.put("diagnostics", diagnostics);
        Path temporary = vault.resolve("vault-manifest.json.tmp");
        progress.accept("Writing manifest: " + entries.size() + " notes");
        try (var writer = Files.newBufferedWriter(temporary, java.nio.charset.StandardCharsets.UTF_8)) {
            JsonOutput.write(manifest, writer);
            writer.write('\n');
        }
        Files.move(temporary, vault.resolve("vault-manifest.json"), StandardCopyOption.ATOMIC_MOVE);
    }

    /** Reports the actual number of entity notes recorded for the final summary. */
    public int noteCount() { return entries.size(); }
}
