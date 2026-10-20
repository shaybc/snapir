package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.model.DiscoveredFile;
import il.co.dcd.composermapper.util.SafePathNames;
import java.nio.file.Path;
import java.util.*;

/** Report definitions which the legacy one-name-per-file layout cannot preserve. */
public final class LegacyVaultCollisionCheck {
    private LegacyVaultCollisionCheck() {}

    public static List<String> find(Path root, List<DiscoveredFile> files, ProcessingReport report) {
        Map<String, String> destinations = new HashMap<>();
        List<String> collisions = new ArrayList<>();
        for (var definition : new ScopedDefinitionCatalog(root, files, report).definitions()) {
            String path = definition.kind() + "/" + SafePathNames.segment(definition.name()).toLowerCase(Locale.ROOT);
            String location = definition.relativePath() + "#" + definition.selector();
            String previous = destinations.putIfAbsent(path, location);
            if (previous != null && !previous.equals(location))
                collisions.add("Legacy vault identity collision at " + path + ": " + previous
                    + " and " + location + ". Use --vault-layout scoped --workspace-id <stable-name> with an empty destination.");
        }
        return collisions;
    }
}
