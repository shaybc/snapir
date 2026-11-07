import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.*;
import java.util.*;

/** Copy an editable operation project and localize external demo assets; never build a different application. */
public final class StandalonePackage {
    public static void main(String[] args) {
        try {packageOperation(Path.of(args[0]));}
        catch(Exception failure) {
            // Configuration/driver failures can contain credentials; keep those values out of console output.
            System.err.println("Operation project packaging failed ("+failure.getClass().getSimpleName()+"). Check the demo binding and assets; existing projects and packages were preserved.");
            System.exit(1);
        }
    }
    static void packageOperation(Path project) throws Exception {
        project=project.toRealPath();
        Path destination=project.resolve(project.getFileName()+".PKG");
        if(Files.exists(destination))throw new IllegalStateException("Move or rename the existing package before packaging again");
        Files.createDirectories(project.resolve("target"));
        Path output=Files.createTempDirectory(project.resolve("target"),"project-stage-").toRealPath();
        if(!output.startsWith(project.resolve("target")))throw new IllegalArgumentException("Package staging escaped target");
        Path nativeProject=Files.isRegularFile(project.resolve("standalone/pom.xml")) ? project.resolve("standalone") : project;
        Path nativeOutput=nativeProject.equals(project) ? output : output.resolve("standalone");
        Map<String,String> originals=sourceHashes(nativeProject);
        PackageSharedDependencies.verify(project);
        ObjectNode binding=(ObjectNode)DemoBinding.JSON.readTree(nativeProject.resolve("standalone/operation.json").toFile());
        if(!binding.path("demo").isObject())throw new IllegalArgumentException("Prepare a complete demo before packaging its assets");
        PackageProjectFiles.stage(project,output);
        PackageSharedDependencies.verify(output);
        // Copy the selected settings without parsing or printing credentials.
        Path configuration=nativeProject.resolve("standalone").resolve(binding.path("runtime_config").asText()).normalize();
        PackageFiles.copy(configuration,nativeOutput.resolve("runtime-config.json"));
        binding.put("runtime_config","../runtime-config.json");
        ObjectNode demo=PackageDemoAssets.stage(nativeProject,nativeOutput,binding);
        PackageMicroserviceValues.stage(nativeProject,nativeOutput,binding);
        Path service=project.resolve("microservice/helm");
        if(Files.isDirectory(service))try(var charts=Files.list(service)) {
            for(Path chart:charts.filter(Files::isDirectory).toList())if(Files.isRegularFile(chart.resolve("values.yaml"))) {
                Path destinationChart=output.resolve(project.relativize(chart));
                PackageMicroserviceValues.stage(chart,destinationChart,binding,nativeOutput.resolve("standalone"),nativeProject);
            }
        }
        ObjectNode files=demo.putObject("operation_files");
        for(var entry:originals.entrySet())files.put(entry.getKey(),entry.getValue());
        DemoBinding.JSON.writerWithDefaultPrettyPrinter().writeValue(nativeOutput.resolve("standalone/operation.json").toFile(),binding);
        new DemoBinding(nativeOutput.resolve("standalone/operation.json"),true);
        if(!originals.equals(sourceHashes(nativeProject)) || !originals.equals(sourceHashes(nativeOutput)))
            throw new IllegalArgumentException("Operation POM or sources changed during packaging");
        for(String name:new String[]{"run-operation.bat","run-operation-demo.bat","package-standalone-operation.bat"})
            if(!DemoBinding.hash((name.equals("package-standalone-operation.bat") ? project : nativeProject).resolve(name)).equals(DemoBinding.hash((name.equals("package-standalone-operation.bat") ? output : nativeOutput).resolve(name))))
                throw new IllegalArgumentException("Project launcher changed during packaging");
        Files.move(output,destination);
        System.out.println("Operation project package created: "+destination);
    }
    static Map<String,String> sourceHashes(Path project) throws Exception {
        Map<String,String> hashes=new TreeMap<>();
        hashes.put("pom.xml",DemoBinding.hash(project.resolve("pom.xml")));
        try(var files=Files.walk(project.resolve("src/main"))) {
            for(Path path:files.filter(Files::isRegularFile).toList())hashes.put(PackageFiles.relative(project,path),DemoBinding.hash(path));
        }
        return hashes;
    }
}
