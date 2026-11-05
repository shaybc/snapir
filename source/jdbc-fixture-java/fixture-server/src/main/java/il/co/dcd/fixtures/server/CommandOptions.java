package il.co.dcd.fixtures.server;

import java.nio.file.*;
import java.util.*;

/** Strict command options shared by foreground startup and external lifecycle commands. */
final class CommandOptions {
    final String command;
    private final Map<String,String> values=new LinkedHashMap<>();
    private final List<Path> roots=new ArrayList<>();
    private final Map<String,Path> relocations=new LinkedHashMap<>();
    CommandOptions(String[] args) {
        if (args.length==0) throw new IllegalArgumentException("A fixture tool command is required");command=args[0];
        if (!Set.of("start","ensure","status","stop","report","verify-fixtures","capabilities").contains(command)) throw new IllegalArgumentException("Unknown fixture tool command");
        for (int i=1;i<args.length;i++) {
            String key=args[i];
            if (key.equals("--debug")) { if(values.put(key,"true")!=null) throw new IllegalArgumentException("Repeated debug option");continue; }
            if (++i==args.length) throw new IllegalArgumentException("Missing option value");
            if (key.equals("--fixture-root")) roots.add(Path.of(args[i]));
            else if(key.equals("--asset-root-map")) {
                String[] mapping=args[i].split("=",2);
                if(mapping.length!=2 || mapping[0].isBlank() || mapping[1].isBlank() || relocations.put(mapping[0],Path.of(mapping[1]))!=null)
                    throw new IllegalArgumentException("Invalid or repeated asset root mapping");
            }
            else if (!Set.of("--host","--port","--catalogue","--expected-hash","--state-dir","--jdbc-url","--startup-timeout-ms","--execution").contains(key)
                    || values.put(key,args[i])!=null) throw new IllegalArgumentException("Unknown or repeated option");
        }
    }
    String required(String key) {
        String value=values.get(key);if(value==null || value.isBlank()) throw new IllegalArgumentException("Required option: "+key);return value;
    }
    String get(String key,String fallback) { return values.getOrDefault(key,fallback); }
    Path state() { return Path.of(required("--state-dir")).toAbsolutePath().normalize(); }
    List<Path> roots() {
        return roots.isEmpty() ? List.of(Path.of(required("--catalogue")).toAbsolutePath().getParent()) : List.copyOf(roots);
    }
    FixtureCatalogue catalogue() throws Exception {
        return new FixtureCatalogue(Path.of(required("--catalogue")),required("--expected-hash"),roots(),relocations);
    }
    List<String> startArguments(String host,int port) {
        List<String> result=new ArrayList<>(List.of("start","--host",host,"--port",Integer.toString(port),"--catalogue",Path.of(required("--catalogue")).toAbsolutePath().toString(),
            "--expected-hash",required("--expected-hash"),"--state-dir",state().toString()));
        for (Path root : roots()) result.addAll(List.of("--fixture-root",root.toAbsolutePath().toString()));
        relocations.forEach((from,to)->result.addAll(List.of("--asset-root-map",from+"="+to.toAbsolutePath())));
        if (values.containsKey("--debug")) result.add("--debug");return result;
    }
}
