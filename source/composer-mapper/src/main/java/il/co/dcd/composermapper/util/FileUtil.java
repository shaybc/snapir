package il.co.dcd.composermapper.util;
import java.io.IOException; import java.nio.charset.StandardCharsets; import java.nio.file.*; import java.security.*;
public final class FileUtil {
  private FileUtil(){}
  public static void writeString(Path p,String c) throws IOException { var analysis=il.co.dcd.composermapper.storage.AnalysisSession.current(); if(analysis!=null&&analysis.stageNote(p,c))return; if(p.getParent()!=null) Files.createDirectories(p.getParent()); Files.writeString(p,c,StandardCharsets.UTF_8); }
  public static String sha256(Path p){ var analysis=il.co.dcd.composermapper.storage.AnalysisSession.current(); if(analysis!=null){String cached=analysis.hash(p);if(cached!=null)return cached;} return rawSha256(p); }
  public static String rawSha256(Path p){ try{ MessageDigest d=MessageDigest.getInstance("SHA-256"); try(var input=Files.newInputStream(p)){byte[] buffer=new byte[65536];int count;while((count=input.read(buffer))!=-1)d.update(buffer,0,count);} byte[] h=d.digest(); return java.util.HexFormat.of().formatHex(h); }catch(Exception e){ return "unavailable"; } }
}
