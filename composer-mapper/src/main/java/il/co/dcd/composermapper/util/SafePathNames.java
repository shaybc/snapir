package il.co.dcd.composermapper.util;

import java.util.Locale;

public final class SafePathNames {
  private SafePathNames(){}
  public static String document(String id){ return segment(id)+".md"; }
  public static String pathWithoutExtension(String folder, String id){ return folder+"/"+segment(id); }
  public static String classPathWithoutExtension(String fqcn){ String[] parts=String.valueOf(fqcn).split("\\."); StringBuilder out=new StringBuilder("classes"); for(String part:parts) out.append("/").append(segment(part)); return out.toString(); }
  public static String segment(String value){
    String raw=String.valueOf(value);
    String safe=raw.replaceAll("[\\x00-\\x1F<>:\"/\\\\|?*\\uFFFD]", "_").replaceAll("_+", "_").trim();
    safe=safe.replaceAll("[. ]+$", "");
    if(safe.isBlank()) safe="unnamed";
    String upper=safe.toUpperCase(Locale.ROOT);
    if(upper.matches("CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]")) safe=safe+"_file";
    if(!safe.equals(raw)) safe=safe+"_"+Integer.toUnsignedString(raw.hashCode(),36);
    return safe;
  }
}
