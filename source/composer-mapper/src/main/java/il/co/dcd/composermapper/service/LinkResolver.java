package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.util.SafePathNames;
import il.co.dcd.composermapper.util.OperationStepFlow;
import il.co.dcd.composermapper.model.OpStepDef;
import java.nio.file.Path;
import java.util.Map;

public class LinkResolver {
  private final boolean markdownLinks;
  private Map<String, String> documents = Map.of();
  private OperationStepFlow stepFlow;

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

  /** Binds the ordered effective steps for scoped links and diagrams. */
  public void setStepFlow(OperationStepFlow flow) { this.stepFlow = flow; }
  public OperationStepFlow stepFlow() { return stepFlow; }

  /** Links an exact occurrence while displaying its original source label. */
  public String stepLink(OpStepDef step) {
    if (step.getOccurrenceKey() == null) return stepLink(step.getId());
    String document = documents.get("opsteps:" + step.getOccurrenceKey());
    return document == null ? "Unresolved: `" + step.getId() + "`"
        : link(document.substring(0, document.length() - 3), step.getId());
  }

  /** Chooses the occurrence-specific writer destination, preserving legacy destinations. */
  public Path stepDocumentPath(Path vault, OpStepDef step) {
    return documentPath(vault, "opsteps", step.getOccurrenceKey() == null ? step.getId() : step.getOccurrenceKey());
  }

  /** Resolves a scoped transition from its source occurrence without changing the label. */
  public String transitionLink(OpStepDef step, String name) {
    OpStepDef target = stepFlow.target(step, name);
    if (target != null) return "`" + name + "` → " + stepLink(target);
    if ("end".equals(name) || "next".equalsIgnoreCase(name)) return "`" + name + "` (end of flow)";
    return "unresolved `" + name + "`";
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
