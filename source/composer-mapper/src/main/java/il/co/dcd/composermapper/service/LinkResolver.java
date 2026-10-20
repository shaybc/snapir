package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.util.SafePathNames;
import java.nio.file.Path;
import java.util.Map;

public class LinkResolver {
  private final boolean markdownLinks;
  private Map<String, String> documents = Map.of();

  public LinkResolver() {
    this(false);
  }

  public LinkResolver(boolean markdownLinks) {
    this.markdownLinks = markdownLinks;
  }

  /** Resolve both writer destinations and links from the same scoped view inventory. */
  public LinkResolver(boolean markdownLinks, Map<String, String> documents) {
    this(markdownLinks);
    this.documents = Map.copyOf(documents);
  }

  public Path documentPath(Path vault, String folder, String id) {
    String fallback = folder.equals("classes") ? SafePathNames.classPathWithoutExtension(id) + ".md"
        : SafePathNames.pathWithoutExtension(folder, id) + ".md";
    return vault.resolve(documents.getOrDefault(folder + ":" + id, fallback));
  }

  private String documentLink(String folder, String id, String fallback) {
    String document = documents.get(folder + ":" + id);
    if (!documents.isEmpty() && document == null) return "Unresolved: `" + id + "`";
    return link(document == null ? fallback : document.substring(0, document.length() - 3), id);
  }

  public String operationLink(String id) {
    return documentLink("operations", id, SafePathNames.pathWithoutExtension("operations", id));
  }

  public String stepLink(String id) {
    return documentLink("opsteps", id, SafePathNames.pathWithoutExtension("opsteps", id));
  }

  public String formatLink(String id) {
    return documentLink("formats", id, SafePathNames.pathWithoutExtension("formats", id));
  }

  public String contextLink(String id) {
    return documentLink("contexts", id, SafePathNames.pathWithoutExtension("contexts", id));
  }

  public String classLink(String fqcn) {
    return documentLink("classes", fqcn, SafePathNames.classPathWithoutExtension(fqcn));
  }

  private String link(String pathWithoutExtension, String label) {
    if (markdownLinks) {
      return "[" + label + "](" + pathWithoutExtension + ".md)";
    }
    return "[[" + pathWithoutExtension + "|" + label + "]]";
  }
}
