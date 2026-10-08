package il.co.dcd.composermapper.index;
import java.nio.file.Path;
import java.util.*;

public record Indexes(
    Map<String,String>      tagToClass,
    Map<String,Path>        tagToSource,
    Map<String,Path>        operationToSource,
    Map<String,Path>        stepToSource,
    Map<String,Path>        formatToSource,
    Map<String,Path>        contextToSource,
    Map<String,Path>        classToSource,
    Map<String,String>      stepToOperation,
    Map<String,String>      stepToImplClass,
    Map<String,Set<String>> operationToFormats,
    Map<String,String>      operationToContext,
    Map<String,Set<String>> classUsedBySteps,
    Map<String,Set<String>> formatUsedByOperations,
    Map<String,Set<String>> contextUsedByOperations,
    // channel-aware registry: operationName → xmlFilePath (from selfDefOper)
    Map<String,String>      channelOperationRegistry,
    // operationName → channelName (from which dse.ini it was registered)
    Map<String,String>      channelForOperation,
    // serviceTag → FQCN
    Map<String,String>      serviceRegistry,
    // ordered list of channel names in the import chain (first = root channel)
    List<String>            dseIniImportChain,
    Set<String>             unresolvedClassRefs,
    Set<String>             unresolvedFormatRefs,
    Set<String>             unresolvedContextRefs
) {
    public static Indexes create() {
        return new Indexes(
            new LinkedHashMap<>(), new LinkedHashMap<>(), new LinkedHashMap<>(),
            new LinkedHashMap<>(), new LinkedHashMap<>(), new LinkedHashMap<>(),
            new LinkedHashMap<>(), new LinkedHashMap<>(), new LinkedHashMap<>(),
            new LinkedHashMap<>(), new LinkedHashMap<>(), new LinkedHashMap<>(),
            new LinkedHashMap<>(), new LinkedHashMap<>(),
            new LinkedHashMap<>(), new LinkedHashMap<>(), new LinkedHashMap<>(),
            new ArrayList<>(),
            new LinkedHashSet<>(), new LinkedHashSet<>(), new LinkedHashSet<>()
        );
    }
}
