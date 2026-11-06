package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.index.JavaClassIndexer;
import il.co.dcd.composermapper.model.DiscoveredFile;
import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import il.co.dcd.composermapper.util.XmlUtil;
import il.co.dcd.composermapper.util.FormatCollectionPolicy;
import il.co.dcd.composermapper.util.ScopedVaultPaths;
import java.nio.file.Path;
import java.util.*;
import org.w3c.dom.Element;

/** Retain source occurrences and resolve only candidates eligible in a channel and operation. */
public final class ScopedDefinitionCatalog {
    private final il.co.dcd.composermapper.storage.AnalysisSession analysis = il.co.dcd.composermapper.storage.AnalysisSession.current();
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
        for (var file : analysis == null ? files.stream().sorted(Comparator.comparing(f -> f.path().toString())).toList() : files) {
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
                index.classToSource().forEach((name, path) -> add(new SourceDefinitionIdentity(
                    "java_class", name, file.channel(), path, relative(root, path), name, "", null)));
            }
        }
        if (analysis != null) {
            for (var definition : definitions()) {
                if (definition.kind().equals("format") && !FormatCollectionPolicy.effective(definition.element()))
                    analysis.store.execute("DELETE FROM definitions WHERE kind=? AND file=? AND selector=?", definition.kind(), definition.file().toString(), definition.selector());
            }
            analysis.store.execute("CREATE TABLE step_positions(file TEXT,selector TEXT,owner TEXT,position INTEGER,group_key TEXT,occurrences INTEGER,PRIMARY KEY(file,selector))");
            analysis.store.execute("CREATE INDEX step_group_keys ON step_positions(file,owner,group_key)");
            analysis.store.execute("INSERT INTO step_positions SELECT file,selector,owner,row_number() OVER(PARTITION BY file,owner ORDER BY ordinal),'',0 FROM definitions WHERE kind='opStep'");
            for(var step:stored("kind='opStep'"))analysis.store.execute("UPDATE step_positions SET group_key=? WHERE file=? AND selector=?",ScopedVaultPaths.stepGroupKey(step.name()),step.file().toString(),step.selector());
            analysis.store.execute("WITH counts AS MATERIALIZED (SELECT file,owner,group_key,count(*) AS total FROM step_positions GROUP BY file,owner,group_key) UPDATE step_positions SET occurrences=(SELECT total FROM counts WHERE counts.file=step_positions.file AND counts.owner=step_positions.owner AND counts.group_key=step_positions.group_key)");
            analysis.store.commit();
            return;
        }
        discardOverriddenFormats();
        for (var definition : definitions) {
            names.computeIfAbsent(definition.kind(), ignored -> new HashMap<>())
                .computeIfAbsent(definition.name(), ignored -> new ArrayList<>()).add(definition);
            if (definition.kind().equals("opStep")) steps.computeIfAbsent(new Owner(definition.file(), definition.owner()),
                ignored -> new ArrayList<>()).add(definition);
        }
    }

    public List<SourceDefinitionIdentity> definitions() { return analysis == null ? List.copyOf(definitions) : stored("1=1"); }

    private void add(SourceDefinitionIdentity definition) {
        if (analysis == null) { definitions.add(definition); return; }
        analysis.store.execute("INSERT INTO definitions(kind,name,channel,file,relative_path,selector,owner,node) VALUES (?,?,?,?,?,?,?,?)",
            definition.kind(), definition.name(), definition.channel(), definition.file().toString(), definition.relativePath(),
            definition.selector(), definition.owner(), il.co.dcd.composermapper.storage.SqlXmlViews.identity(definition.element()));
    }
    private List<SourceDefinitionIdentity> stored(String condition, Object... arguments) {
        return analysis.store.sequence("definitions", condition, arguments, "kind,name,channel,file,relative_path,selector,owner,node", row ->
            new SourceDefinitionIdentity(row[0],row[1],row[2],Path.of(row[3]),row[4],row[5],row[6],
                row[7] == null ? null : (Element)il.co.dcd.composermapper.storage.SqlXmlViews.node(analysis.store,row[7])));
    }
    public int stepPosition(SourceDefinitionIdentity operation,SourceDefinitionIdentity step){return analysis==null?steps(operation).indexOf(step)+1:Integer.parseInt(analysis.store.scalar("SELECT position FROM step_positions WHERE file=? AND selector=?",step.file().toString(),step.selector()));}
    public boolean repeatedStep(SourceDefinitionIdentity operation,SourceDefinitionIdentity step){
        if(analysis==null)return steps(operation).stream().filter(value->ScopedVaultPaths.stepGroupKey(value.name()).equals(ScopedVaultPaths.stepGroupKey(step.name()))).count()>1;
        return Integer.parseInt(analysis.store.scalar("SELECT occurrences FROM step_positions WHERE file=? AND selector=?",step.file().toString(),step.selector()))>1;
    }

    /** Omits formats replaced in a keyed scope, including their nested definitions. */
    private void discardOverriddenFormats() {
        definitions.removeIf(definition -> definition.kind().equals("format")
            && !FormatCollectionPolicy.effective(definition.element()));
    }

    public List<SourceDefinitionIdentity> steps(SourceDefinitionIdentity operation) {
        if (analysis != null) return stored("kind='opStep' AND file=? AND owner=?", operation.file().toString(), operation.selector());
        return List.copyOf(steps.getOrDefault(new Owner(operation.file(), operation.selector()), List.of()));
    }

    public List<SourceDefinitionIdentity> candidates(String kind, String name, List<String> channels,
                                                     SourceDefinitionIdentity operation) {
        return (analysis == null ? names.getOrDefault(kind, Map.of()).getOrDefault(name, List.of()) : stored("kind=? AND name=?",kind,name)).stream()
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
            if (analysis != null) analysis.requireDefinitionBudget(element);
            add(new SourceDefinitionIdentity(kind, name, file.channel(), file.path(),
                relative(root, file.path()), selector, owner, element));
            if (kind.equals("operation")) owner = selector;
        }
        Map<String, Integer> counts = new HashMap<>();
        for (Element child : XmlUtil.childElements(element)) {
            if (analysis != null) {
                String storedSelector=analysis.store.scalar("SELECT selector FROM xml_nodes WHERE id=?",il.co.dcd.composermapper.storage.SqlXmlViews.identity(child));
                walk(root,file,child,storedSelector,owner);
            } else {
                int position = counts.merge(child.getTagName(), 1, Integer::sum);
                walk(root, file, child, selector + "/" + child.getTagName() + "[" + position + "]", owner);
            }
        }
    }

    private static String relative(Path root, Path file) {
        return root.relativize(file).toString().replace('\\', '/');
    }
}
