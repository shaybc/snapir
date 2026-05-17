package il.co.dcd.composermapper.util;

import java.nio.file.Path;

public class XmlParseException extends RuntimeException {
  private final Path path;
  public XmlParseException(Path path, Exception cause){ super("Failed parsing XML: "+path,cause); this.path=path; }
  public Path path(){ return path; }
}
