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
     * Java packages alongside Xml Definition inherit its declared channel under the same src folder.
     *
     * @param root   workspace root path
     * @param channel optional channel filter — includes the selected channel and
     *                its declared imports in parent-before-child order
     */
    public List<DiscoveredFile> discover(Path root, String channel) {
        List<DiscoveredFile> out = new ArrayList<>();
        try (var s = Files.walk(root)) {
            s.filter(Files::isRegularFile).forEach(p -> {
                String lower = p.getFileName().toString().toLowerCase();
                String detectedChannel = extractChannel(p);

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
        assignJavaSourceChannels(out);
        if (channel != null && !channel.isBlank()) {
            List<String> channels = new ChannelImportResolver().resolve(out, channel);
            out.removeIf(file -> file.channel() != null && !channels.contains(file.channel().toUpperCase(Locale.ROOT)));
            out.sort(Comparator.comparingInt(file -> file.channel() == null ? -1 :
                channels.indexOf(file.channel().toUpperCase(Locale.ROOT))));
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

    /** Associate Java packages with the channel declared beneath their containing src folder. */
    private void assignJavaSourceChannels(List<DiscoveredFile> files) {
        Map<Path, Set<String>> sourceChannels = new HashMap<>();
        for (var file : files) {
            if (file.channel() == null || !file.path().getFileName().toString().equalsIgnoreCase("dse.ini")) continue;
            Path channelFolder = file.path().getParent();
            Path channelsFolder = channelFolder.getParent();
            Path definitionsFolder = channelsFolder == null ? null : channelsFolder.getParent();
            Path sourceFolder = definitionsFolder == null ? null : definitionsFolder.getParent();
            if (sourceFolder != null && "Channel".equalsIgnoreCase(channelsFolder.getFileName().toString())
                    && "Xml Definition".equalsIgnoreCase(definitionsFolder.getFileName().toString())
                    && "src".equalsIgnoreCase(sourceFolder.getFileName().toString()))
                sourceChannels.computeIfAbsent(sourceFolder, ignored -> new LinkedHashSet<>()).add(file.channel());
        }
        var iterator = files.listIterator();
        while (iterator.hasNext()) {
            var file = iterator.next();
            if (file.channel() != null || file.type() != DiscoveredFile.FileType.JAVA) continue;
            for (Path parent = file.path().getParent(); parent != null; parent = parent.getParent()) {
                Set<String> channels = sourceChannels.get(parent);
                if (channels == null) continue;
                if (channels.size() == 1)
                    iterator.set(new DiscoveredFile(file.path(), file.type(), channels.iterator().next()));
                break;
            }
        }
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
