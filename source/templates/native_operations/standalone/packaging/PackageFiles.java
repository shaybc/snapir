import java.nio.file.*;
import java.util.*;
import java.util.jar.*;

/** Copy only explicit runtime assets, with containment and collision checks. */
final class PackageFiles {
    static Path inside(Path root,String name) throws Exception {
        Path path=root.resolve(name).normalize().toAbsolutePath();
        if(!path.startsWith(root.toAbsolutePath()) || path.equals(root.toAbsolutePath()))
            throw new IllegalArgumentException("Package path escaped its root");
        return path;
    }
    static void copy(Path source,Path target) throws Exception {
        if(Files.isSymbolicLink(source) || !Files.isRegularFile(source))throw new IllegalArgumentException("Package source must be a regular file");
        Files.createDirectories(target.getParent());
        if(Files.exists(target)) {
            if(!DemoBinding.hash(source).equals(DemoBinding.hash(target)))throw new IllegalArgumentException("Conflicting package file: "+target.getFileName());
        } else Files.copy(source,target);
    }
    static void tree(Path source,Path target) throws Exception {
        Path root=source.toRealPath();
        try(var paths=Files.walk(root)) {
            for(Path path:paths.sorted().toList()) {
                if(Files.isSymbolicLink(path) || !path.toRealPath().startsWith(root))throw new IllegalArgumentException("Package source contains an external link");
                Path destination=target.resolve(root.relativize(path));
                if(Files.isDirectory(path))Files.createDirectories(destination);else copy(path,destination);
            }
        }
    }
    static void library(Path source,Path target) throws Exception {
        try(JarFile jar=new JarFile(source.toFile())) {
            if(jar.getEntry("il/co/dcd/fixtures/jdbc/FixtureDriver.class")!=null ||
               jar.getEntry("il/co/dcd/verification/harness/BoundaryHarness.class")!=null)
                throw new IllegalArgumentException("Demo/test tooling cannot be placed in production lib: "+source.getFileName());
        }
        copy(source,target);
    }
    static String relative(Path directory,Path file) {return directory.relativize(file).toString().replace('\\','/');}
}
