package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.model.DiscoveredFile;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

public class FileDiscoveryService {

    private static final Set<String> KNOWN_NON_COMPOSER_XML = Set.of(
        "ejb-jar.xml", "web.xml", "application.xml", "application-client.xml",
        "ra.xml", "persistence.xml", "beans.xml", "faces-config.xml",
        "validation.xml", "pom.xml");

    /**
     * Discovers all WSBCC source files under root.
     * Extracts channel name from the path structure:
     *   .../Channel/{CHANNEL}/... or .../Channel/{CHANNEL}/dse.ini
     *
     * @param root   workspace root path
     * @param channel optional channel filter — if non-null, only files under
     *                Channel/{channel}/ are included (case-insensitive)
     */
    public List<DiscoveredFile> discover(Path root, String channel) {
        List<DiscoveredFile> out = new ArrayList<>();
        try (var s = Files.walk(root)) {
            s.filter(Files::isRegularFile).forEach(p -> {
                String lower = p.getFileName().toString().toLowerCase();
                String detectedChannel = extractChannel(p);

                // channel filter
                if (channel != null && !channel.isBlank()
                        && detectedChannel != null
                        && !detectedChannel.equalsIgnoreCase(channel)) {
                    return;
                }

                DiscoveredFile.FileType type;
                if (lower.endsWith(".xml") && !isKnownNonComposerXml(lower)) {
                    type = DiscoveredFile.FileType.XML;
                } else if (lower.endsWith(".ini")) {
                    type = DiscoveredFile.FileType.INI;
                } else if (lower.endsWith(".java")) {
                    type = DiscoveredFile.FileType.JAVA;
                } else {
                    return;
                }
                out.add(new DiscoveredFile(p, type, detectedChannel));
            });
        } catch (IOException e) {
            throw new RuntimeException("Failed scanning: " + root, e);
        }
        return out;
    }

    /** Convenience overload — no channel filter. */
    public List<DiscoveredFile> discover(Path root) {
        return discover(root, null);
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private boolean isKnownNonComposerXml(String fileName) {
        return KNOWN_NON_COMPOSER_XML.contains(fileName);
    }

    /**
     * Extracts the channel name from the file path by looking for a
     * "Channel" path segment and returning the next segment.
     * e.g. .../Channel/INTERNET/defaultFile/dseformat.xml → "INTERNET"
     */
    private String extractChannel(Path p) {
        for (int i = 0; i < p.getNameCount() - 1; i++) {
            if ("Channel".equalsIgnoreCase(p.getName(i).toString())) {
                return p.getName(i + 1).toString();
            }
        }
        return null;
    }
}
