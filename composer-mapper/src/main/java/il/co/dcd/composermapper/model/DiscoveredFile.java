package il.co.dcd.composermapper.model; import java.nio.file.Path; public record DiscoveredFile(Path path, FileType type){ public enum FileType{XML,INI,JAVA} }
