package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.Json;
import java.net.*;
import java.nio.file.*;
import java.util.*;

/** Executable tooling entry point; ordinary applications never parse these lifecycle commands. */
public final class FixtureServerCommand {
    private FixtureServerCommand() { }
    public static void main(String[] args) {
        try {System.out.println(new String(Json.bytes(run(new CommandOptions(args))),java.nio.charset.StandardCharsets.UTF_8));}
        catch(Exception error) {
            // Parser/URI errors may contain supplied text; do not echo fixture values or credentials.
            String detail=(error.getClass()==IllegalArgumentException.class || error.getClass()==IllegalStateException.class)
                ? " "+error.getMessage() : " Check command, fixture identity, port ownership and server.log.";
            System.err.println("Fixture tool failed: "+error.getClass().getSimpleName()+"."+detail);
            System.exit(1);
        }
    }
    static Map<String,Object> run(CommandOptions options) throws Exception {
        return switch(options.command) {
            case "capabilities" -> Map.of("outcome","ok","tool_version","1.0.0","protocol",1,"minimum_java",21,
                "fixture_schemas",List.of("test-assets-v1","shared-fixtures-v1","fixture-jdbc-catalogue-v1"),
                "supported",List.of("prepared_queries","callable_scalar_and_cursor_outputs","connection_pool_lifecycle","immutable_fixture_references"),
                "unsupported",List.of("sql_execution","stateful_writes","batch_updates","vendor_unwrap","full_jdbc_compliance"));
            case "verify-fixtures" -> {FixtureCatalogue catalogue=options.catalogue();yield Map.of("outcome","ok","catalogue_hash",catalogue.hash,"scenarios",catalogue.scenarios());}
            case "ensure" -> ServerLifecycle.ensure(options);
            case "status" -> ServerLifecycle.status(options);
            case "stop" -> ServerLifecycle.stop(options);
            case "report" -> ServerLifecycle.report(options);
            case "start" -> start(options);
            default -> throw new IllegalArgumentException("Unknown command");
        };
    }
    private static Map<String,Object> start(CommandOptions options) throws Exception {
        FixtureCatalogue catalogue=options.catalogue();Path directory=options.state();
        int port=Integer.parseInt(options.required("--port"));if(port<1 || port>65535) throw new IllegalArgumentException("Invalid server port");
        String host=options.get("--host","127.0.0.1"),token=UUID.randomUUID().toString();
        try(StateFiles.OwnedLock lock=StateFiles.lock(directory,"server.lock",5000);
            FixtureServer server=new FixtureServer(catalogue,new InetSocketAddress(host,port),token,Boolean.parseBoolean(options.get("--debug","false")),ServerLifecycle.artifactHash(),directory.resolve("reports"))) {
            Map<String,Object> state=new LinkedHashMap<>(server.health());
            state.put("host",host);state.put("port",server.port());state.put("owner_token",token);state.put("status","ready");
            Thread hook=new Thread(server::close);Runtime.getRuntime().addShutdownHook(hook);
            try {
                server.start();StateFiles.write(directory,state);
                System.out.println(Json.canonical(StateFiles.publicState(state)));System.out.flush();server.await();
            }finally {
                state.put("status","stopped");StateFiles.write(directory,state);
                try {Runtime.getRuntime().removeShutdownHook(hook);}catch(IllegalStateException ignored) { }
            }
            return Map.of("outcome","ok","stopped",true);
        }
    }
}
