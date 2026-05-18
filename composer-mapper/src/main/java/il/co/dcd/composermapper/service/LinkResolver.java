package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.util.SafePathNames;

public class LinkResolver {
  private final boolean markdownLinks;

  public LinkResolver() {
    this(false);
  }

  public LinkResolver(boolean markdownLinks) {
    this.markdownLinks = markdownLinks;
  }

  public String operationLink(String id) {
    return link(SafePathNames.pathWithoutExtension("operations", id), id);
  }

  public String stepLink(String id) {
    return link(SafePathNames.pathWithoutExtension("opsteps", id), id);
  }

  public String formatLink(String id) {
    return link(SafePathNames.pathWithoutExtension("formats", id), id);
  }

  public String contextLink(String id) {
    return link(SafePathNames.pathWithoutExtension("contexts", id), id);
  }

  public String classLink(String fqcn) {
    return link(SafePathNames.classPathWithoutExtension(fqcn), fqcn);
  }

  private String link(String pathWithoutExtension, String label) {
    if (markdownLinks) {
      return "[" + label + "](" + pathWithoutExtension + ".md)";
    }
    return "[[" + pathWithoutExtension + "|" + label + "]]";
  }
}
