package il.co.dcd.composermapper.index;

import il.co.dcd.composermapper.util.XmlUtil;
import org.w3c.dom.Element;

import java.nio.file.Path;
import java.util.List;

/**
 * Parses a WSBCC dse.ini XML file and populates Indexes with:
 * - tag → FQCN mappings (from tags/formats, tags/opSteps, tags/operations, tags/services)
 * - selfDefOper operation registry (operationName → xmlFilePath)
 * - import chain
 * - service registry
 *
 * The channel name is extracted from the dse.ini file path structure:
 *   .../Channel/{CHANNEL}/dse.ini
 */
public class IniMappingIndexer {

    public void index(Path iniFile, Indexes x) {
        String channel = extractChannel(iniFile);

        Element root;
        try {
            root = XmlUtil.parse(iniFile).getDocumentElement();
        } catch (Exception e) {
            // not a valid XML dse.ini — skip silently
            return;
        }

        // Record import chain
        Element importColl = findKColl(root, "import");
        if (importColl != null) {
            for (Element field : XmlUtil.childElements(importColl)) {
                if ("field".equals(field.getTagName())) {
                    String importedChannel = XmlUtil.attr(field, "id");
                    if (importedChannel != null && !importedChannel.isBlank()
                            && !x.dseIniImportChain().contains(importedChannel)) {
                        x.dseIniImportChain().add(importedChannel);
                    }
                }
            }
        }

        Element settings = findKColl(root, "settings");
        if (settings == null) return;

        // selfDefOper — operation registry for this channel
        Element files = findKColl(settings, "files");
        if (files != null) {
            Element selfDefOper = findKColl(files, "selfDefOper");
            if (selfDefOper != null) {
                for (Element operDef : XmlUtil.childElements(selfDefOper)) {
                    if ("operDef".equals(operDef.getTagName())) {
                        String filePath = XmlUtil.attr(operDef, "id");
                        String opName   = XmlUtil.attr(operDef, "value");
                        if (opName != null && !opName.isBlank()
                                && filePath != null && !filePath.isBlank()) {
                            x.channelOperationRegistry().put(opName, filePath);
                            x.channelForOperation().put(opName, channel != null ? channel : "unknown");
                        }
                    }
                }
            }
        }

        // tags section
        Element tags = findKColl(settings, "tags");
        if (tags == null) return;

        // formats section: contains both decorators and formatters
        Element formats = findKColl(tags, "formats");
        if (formats != null) {
            indexFields(formats, iniFile, x);
        }

        // opSteps section
        Element opSteps = findKColl(tags, "opSteps");
        if (opSteps != null) {
            indexFields(opSteps, iniFile, x);
        }

        // operations section
        Element operations = findKColl(tags, "operations");
        if (operations != null) {
            indexFields(operations, iniFile, x);
        }

        // services section
        Element services = findKColl(tags, "services");
        if (services != null) {
            for (Element field : XmlUtil.childElements(services)) {
                if ("field".equals(field.getTagName())) {
                    String tag  = XmlUtil.attr(field, "id");
                    String fqcn = XmlUtil.attr(field, "value");
                    if (tag != null && !tag.isBlank() && fqcn != null && !fqcn.isBlank()) {
                        x.serviceRegistry().put(tag, fqcn);
                    }
                }
            }
        }

        // data, contexts, processors, types — currently empty in all observed dse.ini files
        // index them the same way in case they are populated in other installations
        for (String section : List.of("data", "contexts", "processors", "types")) {
            Element el = findKColl(tags, section);
            if (el != null) indexFields(el, iniFile, x);
        }
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private void indexFields(Element parent, Path iniFile, Indexes x) {
        for (Element el : XmlUtil.childElements(parent)) {
            if ("field".equals(el.getTagName())) {
                String tag  = XmlUtil.attr(el, "id");
                String fqcn = XmlUtil.attr(el, "value");
                if (tag != null && !tag.isBlank() && fqcn != null && !fqcn.isBlank()) {
                    x.tagToClass().put(tag, fqcn);
                    x.tagToSource().put(tag, iniFile);
                }
            }
        }
    }

    /**
     * Finds a direct or nested kColl element by id within parent.
     * Searches only immediate children.
     */
    private Element findKColl(Element parent, String id) {
        for (Element child : XmlUtil.childElements(parent)) {
            if ("kColl".equals(child.getTagName()) && id.equals(XmlUtil.attr(child, "id"))) {
                return child;
            }
        }
        return null;
    }

    /**
     * Extracts the channel name from the dse.ini file path.
     * Expected structure: .../Channel/{CHANNEL}/dse.ini
     * Falls back to the parent directory name.
     */
    private String extractChannel(Path iniFile) {
        Path parent = iniFile.getParent();
        if (parent == null) return null;
        return parent.getFileName().toString();
    }
}
