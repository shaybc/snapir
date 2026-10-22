package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.model.DiscoveredFile;
import il.co.dcd.composermapper.util.XmlUtil;
import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.index.IniMappingIndexer;
import java.nio.file.Path;
import java.util.*;

/** Resolves the implicit XML base and declared dependencies before the consuming channel. */
public class ChannelImportResolver {
    /** Builds tag mappings with XML defaults, declared imports, then local overrides. */
    public Map<String, String> tagMappings(List<DiscoveredFile> files, String channel) {
        Indexes index = Indexes.create();
        IniMappingIndexer indexer = new IniMappingIndexer();
        for (String dependency : resolve(files, channel)) {
            for (var file : files) {
                if (file.channel() != null && dependency.equalsIgnoreCase(file.channel()) &&
                        file.path().getFileName().toString().equalsIgnoreCase("dse.ini"))
                    indexer.index(file.path(), index);
            }
        }
        return index.tagToClass();
    }

    public List<String> resolve(List<DiscoveredFile> files, String channel) {
        Map<String, Path> definitions = new LinkedHashMap<>();
        for (var file : files) {
            if (file.channel() == null || !file.path().getFileName().toString().equalsIgnoreCase("dse.ini")) continue;
            String name = file.channel().toUpperCase(Locale.ROOT);
            if (definitions.putIfAbsent(name, file.path()) != null)
                throw new IllegalArgumentException("Multiple dse.ini definitions for channel " + name);
        }
        List<String> ordered = new ArrayList<>();
        String consuming = channel.toUpperCase(Locale.ROOT);
        if (!consuming.equals("XML")) {
            if (!definitions.containsKey("XML"))
                throw new IllegalArgumentException("Missing implicit XML base channel definition for " + consuming
                    + ": include the XML channel's dse.ini and sources in the mapping root");
            visit("XML", definitions, new HashSet<>(), ordered);
        }
        visit(consuming, definitions, new HashSet<>(), ordered);
        if (!consuming.equals("XML")) {
            // Implicit inheritance is a base layer, not a recursive import edge.
            ordered.remove("XML");
            ordered.addFirst("XML");
            ordered.remove(consuming);
            ordered.add(consuming);
        }
        return ordered;
    }

    private void visit(String channel, Map<String, Path> definitions, Set<String> active, List<String> ordered) {
        if (ordered.contains(channel)) return;
        if (!active.add(channel)) throw new IllegalArgumentException("Channel import cycle at " + channel);
        Path definition = definitions.get(channel);
        if (definition == null) throw new IllegalArgumentException("Missing imported channel definition: " + channel);
        var root = XmlUtil.parse(definition).getDocumentElement();
        for (var collection : XmlUtil.childElements(root)) {
            if (!"kColl".equals(collection.getTagName()) || !"import".equals(XmlUtil.attr(collection, "id"))) continue;
            for (var field : XmlUtil.childElements(collection)) {
                String imported = XmlUtil.attr(field, "id");
                if ("field".equals(field.getTagName()) && imported != null && !imported.isBlank())
                    visit(imported.toUpperCase(Locale.ROOT), definitions, active, ordered);
            }
        }
        active.remove(channel);
        ordered.add(channel);
    }
}
