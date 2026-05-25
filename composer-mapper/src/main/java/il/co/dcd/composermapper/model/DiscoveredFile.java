package il.co.dcd.composermapper.model;
import java.nio.file.Path;
public record DiscoveredFile(Path path, FileType type, String channel) {
    public enum FileType { XML, INI, JAVA }
    public DiscoveredFile(Path path, FileType type) { this(path, type, null); }
}
