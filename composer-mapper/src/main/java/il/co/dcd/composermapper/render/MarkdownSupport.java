package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.model.TagNode;

public final class MarkdownSupport {
  private MarkdownSupport(){}

  public static String bullet(String v){ return "- "+v+System.lineSeparator(); }
  public static String code(String v){ return "`"+v+"`"; }

  public static String mermaidNodeId(String value) {
    String raw = value == null || value.isBlank() ? "blank" : value;
    String safe = raw.replaceAll("[^A-Za-z0-9_]", "_").replaceAll("_+", "_");
    safe = safe.replaceAll("^_+|_+$", "");
    if (safe.isBlank()) safe = "node";
    return "m_" + safe + "_" + Integer.toUnsignedString(raw.hashCode(), 36);
  }

  public static String mermaidLabel(String value) {
    return "[\"" + mermaidText(value) + "\"]";
  }

  public static String mermaidEdgeLabel(String value) {
    return "|\"" + mermaidText(value).replace("|", "\\|") + "\"|";
  }

  private static String mermaidText(String value) {
    String text = avoidMermaidKeyword(value == null ? "" : value);
    return text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .replace("<br>", "\n")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n");
  }

  private static String avoidMermaidKeyword(String value) {
    String trimmed = value.trim();
    if (trimmed.equals("end")) return value.replace("end", "End");
    if (trimmed.equals("default")) return value.replace("default", "Default");
    return value;
  }

  public static String tagTree(TagNode n,int level){ if(n==null) return ""; String indent="  ".repeat(Math.max(0,level)); StringBuilder sb=new StringBuilder(); sb.append(indent).append("<").append(n.getTagName()); n.getAttributes().forEach((k,v)->sb.append(" ").append(k).append("=\"").append(v).append("\"")); if(n.getChildren().isEmpty()){ sb.append("/>\n"); return sb.toString(); } sb.append(">\n"); for(TagNode c:n.getChildren()) sb.append(tagTree(c,level+1)); sb.append(indent).append("</").append(n.getTagName()).append(">\n"); return sb.toString(); } }
