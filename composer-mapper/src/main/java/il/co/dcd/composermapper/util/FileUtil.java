package il.co.dcd.composermapper.util;
import java.io.IOException; import java.nio.charset.StandardCharsets; import java.nio.file.*; import java.security.*;
public final class FileUtil {
  private FileUtil(){}
  public static void writeString(Path p,String c) throws IOException { if(p.getParent()!=null) Files.createDirectories(p.getParent()); Files.writeString(p,c,StandardCharsets.UTF_8); }
  public static String sha256(Path p){ try{ byte[] b=Files.readAllBytes(p); MessageDigest d=MessageDigest.getInstance("SHA-256"); byte[] h=d.digest(b); StringBuilder s=new StringBuilder(); for(byte x:h)s.append(String.format("%02x",x)); return s.toString(); }catch(Exception e){ return "unavailable"; } }
}
