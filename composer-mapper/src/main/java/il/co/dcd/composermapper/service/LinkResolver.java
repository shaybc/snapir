package il.co.dcd.composermapper.service;

public class LinkResolver {
  private final boolean markdownLinks;

  public LinkResolver() {
    this(false);
  }

  public LinkResolver(boolean markdownLinks) {
    this.markdownLinks = markdownLinks;
  }

  public String operationLink(String id) {
    return link("operations/" + id, id);
  }

  public String stepLink(String id) {
    return link("opsteps/" + id, id);
  }

  public String formatLink(String id) {
    return link("formats/" + id, id);
  }

  public String contextLink(String id) {
    return link("contexts/" + id, id);
  }

  public String classLink(String fqcn) {
    return link("classes/" + fqcn.replace('.', '/'), fqcn);
  }

  private String link(String pathWithoutExtension, String label) {
    if (markdownLinks) {
      return "[" + label + "](" + pathWithoutExtension + ".md)";
    }
    return "[[" + pathWithoutExtension + "|" + label + "]]";
  }
}
