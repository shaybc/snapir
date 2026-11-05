import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.*;
import java.util.*;
import org.yaml.snakeyaml.*;
import org.yaml.snakeyaml.constructor.SafeConstructor;

/** Preserve editable Helm values while relocating only local driver and fixture references. */
final class PackageMicroserviceValues {
    static void stage(Path project,Path output,ObjectNode binding) throws Exception {
        Path production=project.resolve("values.yaml");
        Map<String,Object> values=read(production);
        Map<String,Object> image=section(values,"image");
        Map<String,Object> driver=section(image,"jdbcDriver");
        String driverPath=Objects.toString(driver.get("path"),"");
        if(!driverPath.isBlank()) {
            Path source=project.resolve(driverPath).normalize().toRealPath();
            if(!DemoBinding.hash(source).equals(driver.get("sha256")))
                throw new IllegalArgumentException("Production JDBC driver changed");
            Path target=output.resolve("lib").resolve(source.getFileName());
            PackageFiles.library(source,target);
            driver.put("path",PackageFiles.relative(output,target));
            write(output.resolve("values.yaml"),values);
        } else PackageFiles.copy(production,output.resolve("values.yaml"));
        Path overlay=project.resolve("demo-values.yaml");
        if(!Files.isRegularFile(overlay))return;
        Map<String,Object> demoValues=read(overlay);
        JsonNode demo=binding.path("demo");
        Path standalone=output.resolve("standalone");
        Path tool=standalone.resolve(demo.path("tool_root").asText()).normalize();
        Map<String,Object> demoDriver=section(section(demoValues,"image"),"jdbcDriver");
        demoDriver.put("path",PackageFiles.relative(output,tool.resolve(demo.path("driver_jar").asText())));
        Map<String,Object> infrastructure=section(demoValues,"demoInfrastructure");
        infrastructure.put("toolRoot",PackageFiles.relative(output,tool));
        Path catalogue=standalone.resolve(demo.path("fixture_catalogue").asText()).normalize();
        infrastructure.put("catalogue",PackageFiles.relative(output,catalogue));
        infrastructure.put("catalogueHash",demo.path("catalogue_hash").asText());
        // Container mount paths remain user settings; only their catalogue-reference keys move.
        Map<String,Object> mounts=section(infrastructure,"assetRootMap");
        if(!mounts.isEmpty()) {
            JsonNode originalBinding=DemoBinding.JSON.readTree(project.resolve("standalone/operation.json").toFile());
            Path originalCatalogue=project.resolve("standalone").resolve(originalBinding.path("demo").path("fixture_catalogue").asText()).normalize();
            JsonNode original=DemoBinding.JSON.readTree(originalCatalogue.toFile());
            Map<String,Object> relocated=new LinkedHashMap<>();
            for(JsonNode scenario:original.path("scenarios"))for(JsonNode resource:scenario.path("resources"))for(JsonNode reference:resource.path("fixtures")) {
                String old=reference.path("asset_root").asText();
                if(mounts.containsKey(old)) {
                    String key="fixtures/"+reference.path("manifest_hash").asText();
                    Object previous=relocated.put(key,mounts.get(old));
                    if(previous!=null&&!previous.equals(mounts.get(old)))throw new IllegalArgumentException("Conflicting fixture mount relocation");
                }
            }
            if(!relocated.isEmpty()) {
                // Retain unmatched settings rather than silently deleting user-provided mounts.
                for(var entry:mounts.entrySet()) {
                    boolean used=false;
                    for(JsonNode scenario:original.path("scenarios"))for(JsonNode resource:scenario.path("resources"))for(JsonNode reference:resource.path("fixtures"))
                        used|=entry.getKey().equals(reference.path("asset_root").asText());
                    if(!used)relocated.put(entry.getKey(),entry.getValue());
                }
                infrastructure.put("assetRootMap",relocated);
            }
        }
        write(output.resolve("demo-values.yaml"),demoValues);
    }
    @SuppressWarnings("unchecked")
    static Map<String,Object> section(Map<String,Object> parent,String name) {
        Object value=parent.get(name);
        if(value==null) {Map<String,Object> result=new LinkedHashMap<>();parent.put(name,result);return result;}
        if(!(value instanceof Map))throw new IllegalArgumentException("Expected YAML mapping: "+name);
        return (Map<String,Object>)value;
    }
    @SuppressWarnings("unchecked")
    static Map<String,Object> read(Path path) throws Exception {
        LoaderOptions options=new LoaderOptions();options.setAllowDuplicateKeys(false);
        Object value=new Yaml(new SafeConstructor(options)).load(Files.readString(path));
        if(!(value instanceof Map))throw new IllegalArgumentException("Expected values mapping");
        return (Map<String,Object>)value;
    }
    static void write(Path path,Map<String,Object> values) throws Exception {
        DumperOptions options=new DumperOptions();options.setDefaultFlowStyle(DumperOptions.FlowStyle.BLOCK);
        Files.writeString(path,new Yaml(options).dump(values));
    }
}
