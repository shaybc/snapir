package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.index.JavaClassIndexer;
import il.co.dcd.composermapper.model.DiscoveredFile;
import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import il.co.dcd.composermapper.util.XmlUtil;
import java.nio.file.Path;
import java.util.*;
import org.w3c.dom.Element;

/** Retain source occurrences and resolve only candidates eligible in a channel and operation. */
public final class ScopedDefinitionCatalog {
    private final List<SourceDefinitionIdentity> definitions = new ArrayList<>();
    private final Map<String, Map<String, List<SourceDefinitionIdentity>>> names = new HashMap<>();
    private final Map<Owner, List<SourceDefinitionIdentity>> steps = new HashMap<>();
    private record Owner(Path file, String selector) {}

    public ScopedDefinitionCatalog(Path root, List<DiscoveredFile> files, ProcessingReport report) {
        this(root, files, report, message -> {});
    }

    /** Catalogs the same source occurrences while reporting indexing progress. */
    public ScopedDefinitionCatalog(Path root, List<DiscoveredFile> files, ProcessingReport report,
                                   java.util.function.Consumer<String> progress) {
        int processed = 0;
        for (var file : files.stream().sorted(Comparator.comparing(f -> f.path().toString())).toList()) {
            processed++;
            if (processed == 1 || processed % 100 == 0 || processed == files.size())
                progress.accept("Indexing source " + processed + "/" + files.size() + ": " + file.path());
            if (file.type() == DiscoveredFile.FileType.XML) {
                try {
                    Element element = XmlUtil.parse(file.path()).getDocumentElement();
                    walk(root, file, element, "/" + element.getTagName() + "[1]", "");
                } catch (il.co.dcd.composermapper.util.XmlParseException e) {
                    report.recordXmlFailure(file.path(), e);
                }
            } else if (file.type() == DiscoveredFile.FileType.JAVA) {
                Indexes index = Indexes.create();
                new JavaClassIndexer().index(file.path(), index);
                index.classToSource().forEach((name, path) -> definitions.add(new SourceDefinitionIdentity(
                    "java_class", name, file.channel(), path, relative(root, path), name, "", null)));
            }
        }
        for (var definition : definitions) {
            names.computeIfAbsent(definition.kind(), ignored -> new HashMap<>())
                .computeIfAbsent(definition.name(), ignored -> new ArrayList<>()).add(definition);
            if (definition.kind().equals("opStep")) steps.computeIfAbsent(new Owner(definition.file(), definition.owner()),
                ignored -> new ArrayList<>()).add(definition);
        }
    }

    public List<SourceDefinitionIdentity> definitions() { return List.copyOf(definitions); }

    public List<SourceDefinitionIdentity> steps(SourceDefinitionIdentity operation) {
        return List.copyOf(steps.getOrDefault(new Owner(operation.file(), operation.selector()), List.of()));
    }

    public List<SourceDefinitionIdentity> candidates(String kind, String name, List<String> channels,
                                                     SourceDefinitionIdentity operation) {
        return names.getOrDefault(kind, Map.of()).getOrDefault(name, List.of()).stream()
            .filter(d -> d.channel() == null || channels.contains(d.channel().toUpperCase(Locale.ROOT)))
            .filter(d -> d.owner().isEmpty() || operation != null && d.file().equals(operation.file())
                && d.owner().equals(operation.selector())).toList();
    }

    /** Inline definitions win only inside their owner; channel imports retain declared order. */
    public SourceDefinitionIdentity resolve(String kind, String name, List<String> channels,
                                             SourceDefinitionIdentity operation) {
        var candidates = candidates(kind, name, channels, operation);
        if (candidates.isEmpty()) return null;
        int rank = candidates.stream().mapToInt(d -> rank(d, channels)).max().orElse(-1);
        var selected = candidates.stream().filter(d -> rank(d, channels) == rank).toList();
        if (selected.size() != 1) throw new IllegalArgumentException("Ambiguous " + kind + " " + name
            + ": " + selected.stream().map(d -> d.relativePath() + "#" + d.selector()).toList());
        return selected.getFirst();
    }

    private int rank(SourceDefinitionIdentity d, List<String> channels) {
        if (!d.owner().isEmpty()) return channels.size() + 1;
        return d.channel() == null ? -1 : channels.indexOf(d.channel().toUpperCase(Locale.ROOT));
    }

    private void walk(Path root, DiscoveredFile file, Element element, String selector, String owner) {
        String kind = switch (element.getTagName()) {
            case "CCDSEServerOperation" -> "operation";
            case "opStep" -> "opStep";
            case "fmtDef" -> "format";
            case "context" -> "context";
            default -> null;
        };
        String name = XmlUtil.attr(element, "id");
        if (kind != null && name != null && !name.isBlank()) {
            definitions.add(new SourceDefinitionIdentity(kind, name, file.channel(), file.path(),
                relative(root, file.path()), selector, owner, element));
            if (kind.equals("operation")) owner = selector;
        }
        Map<String, Integer> counts = new HashMap<>();
        for (Element child : XmlUtil.childElements(element)) {
            int position = counts.merge(child.getTagName(), 1, Integer::sum);
            walk(root, file, child, selector + "/" + child.getTagName() + "[" + position + "]", owner);
        }
    }

    private static String relative(Path root, Path file) {
        return root.relativize(file).toString().replace('\\', '/');
    }
}
