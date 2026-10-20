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
    private final List<Map<String, Object>> entries = new ArrayList<>();
    private final Set<String> paths = new HashSet<>();

    public VaultManifestWriter(String workspace) { this.workspace = workspace; }

    public Map<String, Object> record(Path vault, SourceDefinitionIdentity source, String channel,
            String operation, String operationIdentity, String path, Map<String, Object> extra) throws IOException {
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
        String metadata = "vault_schema_version: 2\nqualified_entity_id: " + definition + "\nusage_id: " + usage
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
        Map<String, Set<String>> consumersByDefinition = new HashMap<>();
        for (var entry : entries) {
            String operation = entry.get("operation_identity").toString();
            if (!operation.isBlank()) consumersByDefinition.computeIfAbsent(entry.get("definition_id").toString(),
                ignored -> new TreeSet<>()).add(operation);
        }
        for (var entry : entries) {
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
        manifest.put("vault_schema_version", 2); manifest.put("identity_version", 1);
        manifest.put("producer", "composer-mapper"); manifest.put("complete", true);
        manifest.put("workspace_id", workspace); manifest.put("channels", channels);
        manifest.put("entities", entries); manifest.put("diagnostics", diagnostics);
        Path temporary = vault.resolve("vault-manifest.json.tmp");
        FileUtil.writeString(temporary, JsonOutput.encode(manifest) + "\n");
        Files.move(temporary, vault.resolve("vault-manifest.json"), StandardCopyOption.ATOMIC_MOVE);
    }
}
