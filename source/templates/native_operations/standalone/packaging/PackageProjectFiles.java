import java.nio.file.*;

/** Copy the operation project as-is, excluding generated output and converter-only records. */
final class PackageProjectFiles {
    static void stage(Path project,Path output) throws Exception {
        try(var files=Files.newDirectoryStream(project)) {
            for(Path path:files) {
                String name=path.getFileName().toString();
                if(excluded(name))continue;
                copy(path,output.resolve(name));
            }
        }
    }
    static boolean excluded(String name) {
        return name.equals("target") || name.equals(".git") || name.endsWith(".PKG") ||
            name.equals(".demo-runtime") || name.equals(".converter-demo") ||
            name.equals(".demo-scenario-generation") || name.equals(".demo-scenario-verification") ||
            name.equals(".demo-owned-files.json") || name.equals("demo-preparation.json") ||
            name.equals("operation-demo-scenarios.json");
    }
    static void copy(Path source,Path target) throws Exception {
        if(Files.isSymbolicLink(source))throw new IllegalArgumentException("Project contains an external link");
        if(!Files.isDirectory(source)) {PackageFiles.copy(source,target);return;}
        Files.createDirectories(target);
        try(var files=Files.newDirectoryStream(source)) {
            for(Path path:files)if(!excluded(path.getFileName().toString()))copy(path,target.resolve(path.getFileName()));
        }
    }
}
