package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.*;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;

/** Local process control verifies PID start, server instance, tool bytes and catalogue before reuse/stop. */
final class ServerLifecycle {
    private ServerLifecycle() { }
    static Path artifact() throws Exception {
        return Path.of(FixtureServerCommand.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
    }
    static String artifactHash() throws Exception {
        Path path=artifact();return Files.isRegularFile(path) ? Json.hash(Files.readAllBytes(path)) : "development";
    }
    static Map<String,Object> request(URI address,String method,String path,Object body) throws Exception {
        HttpRequest request=HttpRequest.newBuilder(address.resolve(path)).timeout(Duration.ofSeconds(2))
            .method(method,body==null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(Json.bytes(body))).build();
        try(HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1)).build()) {
            HttpResponse<InputStream> response=client.send(request,HttpResponse.BodyHandlers.ofInputStream());
            byte[] bytes;try(InputStream input=response.body()) { bytes=input.readNBytes(Json.MAX_BYTES+1); }
            if(response.statusCode()!=200) throw new IllegalStateException("Fixture service did not accept command");
            Map<String,Object> result=Json.object(Json.read(bytes));
            if(!"ok".equals(result.get("outcome"))) throw new IllegalStateException("Fixture service command failed");return result;
        }
    }
    private static URI address(Map<String,Object> state) throws URISyntaxException {
        InetAddress host;
        try {host=InetAddress.getByName((String)state.get("host"));}catch(Exception e){throw new IllegalStateException("Invalid owned server address");}
        if(!host.isLoopbackAddress()) throw new IllegalStateException("Local lifecycle requires loopback host");
        return new URI("http",null,host.getHostAddress(),((Number)state.get("port")).intValue(),null,null,null);
    }
    static Map<String,Object> live(Map<String,Object> state) throws Exception {
        if(state.isEmpty()) throw new IllegalStateException("No fixture server state");
        ProcessHandle process=ProcessHandle.of(((Number)state.get("pid")).longValue()).orElseThrow(()->new IllegalStateException("Stale fixture process"));
        if(!process.isAlive() || !process.info().startInstant().orElseThrow().toString().equals(state.get("process_start")))
            throw new IllegalStateException("Fixture process ownership changed");
        Map<String,Object> health=request(address(state),"GET","/v1/health",null);
        verifyHealth(state,health);
        return health;
    }
    private static void verifyHealth(Map<String,Object> state,Map<String,Object> health) {
        for(String field : List.of("server","catalogue_hash","artifact_hash","pid","process_start"))
            if(!Objects.equals(state.get(field),health.get(field))) throw new IllegalStateException("Fixture server ownership mismatch");
        if(!Integer.valueOf(1).equals(health.get("protocol")) || !Boolean.TRUE.equals(health.get("ready"))) throw new IllegalStateException("Fixture protocol/readiness mismatch");
    }
    static Map<String,Object> ensure(CommandOptions options) throws Exception {
        FixtureUrl url=FixtureUrl.parse(options.required("--jdbc-url"));
        if(!url.local()) throw new IllegalArgumentException("Cannot auto-start a remote fixture server");
        FixtureCatalogue catalogue=options.catalogue();catalogue.resource(url.scenario(),url.resource());
        long timeout=Long.parseLong(options.get("--startup-timeout-ms","15000"));if(timeout<100 || timeout>120000) throw new IllegalArgumentException("Invalid startup timeout");
        Path directory=options.state();
        try(StateFiles.OwnedLock lock=StateFiles.lock(directory,"control.lock",timeout)) {
            Map<String,Object> existing=StateFiles.read(directory);boolean active=false;
            if(!existing.isEmpty()) try {live(existing);active=true;}catch(Exception ignored) { }
            if(active) {
                if(!catalogue.hash.equals(existing.get("catalogue_hash")) || !artifactHash().equals(existing.get("artifact_hash"))
                    || url.endpoint().getPort()!=((Number)existing.get("port")).intValue()
                    || !InetAddress.getByName(url.endpoint().getHost()).equals(InetAddress.getByName((String)existing.get("host"))))
                    throw new IllegalStateException("Existing fixture server is incompatible");
                Map<String,Object> result=StateFiles.publicState(existing);result.put("reused",true);result.put("outcome","ok");return result;
            }
            try(Socket socket=new Socket()) {socket.connect(new InetSocketAddress(url.endpoint().getHost(),url.endpoint().getPort()),300);throw new IllegalStateException("Fixture port is occupied by an unowned process");}
            catch(ConnectException | SocketTimeoutException ignored) { }
            Path jar=artifact();if(!Files.isRegularFile(jar)) throw new IllegalStateException("Background startup requires the packaged server JAR");
            String suffix=System.getProperty("os.name").startsWith("Windows") ? ".exe" : "";
            List<String> command=new ArrayList<>(List.of(Path.of(System.getProperty("java.home"),"bin","java"+suffix).toString(),"-jar",jar.toString()));
            command.addAll(options.startArguments(url.endpoint().getHost(),url.endpoint().getPort()));
            Process process=new ProcessBuilder(command).redirectErrorStream(true).redirectOutput(ProcessBuilder.Redirect.appendTo(directory.resolve("server.log").toFile())).start();
            long end=System.nanoTime()+java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(timeout);
            String pending="Server has not published its state";
            try {
                do {
                    if(!process.isAlive()) throw new IllegalStateException("Fixture server exited before readiness; inspect server.log");
                    try {
                        Map<String,Object> state=StateFiles.read(directory);
                        // This exact Process object proves startup ownership; later reuse/stop
                        // still performs the independent OS PID/start lookup in live().
                        if(state.isEmpty() || ((Number)state.get("pid")).longValue()!=process.pid())throw new IllegalStateException("Waiting for launched process state");
                        verifyHealth(state,request(address(state),"GET","/v1/health",null));
                        if(((Number)state.get("pid")).longValue()==process.pid() && catalogue.hash.equals(state.get("catalogue_hash")) && artifactHash().equals(state.get("artifact_hash"))) {
                            if(!process.isAlive())throw new IllegalStateException("Launched fixture server exited");
                            Map<String,Object> result=StateFiles.publicState(state);result.put("reused",false);result.put("outcome","ok");return result;
                        }
                    }catch(Exception failure) { pending=failure.getClass().getSimpleName()+": "+(failure.getClass()==IllegalStateException.class ? failure.getMessage() : "Readiness verification did not complete"); }
                    Thread.sleep(50);
                } while(System.nanoTime()<end);
                throw new IllegalStateException("Fixture readiness timed out ("+pending+"); inspect server.log");
            }catch(Exception e) {process.destroy();process.waitFor(3,java.util.concurrent.TimeUnit.SECONDS);if(process.isAlive()) process.destroyForcibly();throw e;}
        }
    }
    static Map<String,Object> status(CommandOptions options) throws Exception {
        Map<String,Object> state=StateFiles.read(options.state());live(state);
        Map<String,Object> result=StateFiles.publicState(state);result.put("outcome","ok");return result;
    }
    static Map<String,Object> stop(CommandOptions options) throws Exception {
        try(StateFiles.OwnedLock lock=StateFiles.lock(options.state(),"control.lock",5000)) {
            Map<String,Object> state=StateFiles.read(options.state());live(state);
            request(address(state),"POST","/v1/shutdown",Map.of("token",state.get("owner_token")));
            long end=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(5);
            do {try{live(state);}catch(Exception stopped){return Map.of("outcome","ok","stopped",true);}Thread.sleep(50);}while(System.nanoTime()<end);
            throw new IllegalStateException("Owned fixture server did not stop within timeout");
        }
    }
    static Map<String,Object> report(CommandOptions options) throws Exception {
        String id=options.required("--execution");if(!id.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")) throw new IllegalArgumentException("Invalid execution ID");
        Map<String,Object> state=StateFiles.read(options.state());
        String instance=String.valueOf(state.get("server"));if(!instance.matches("[a-f0-9-]{36}"))throw new IllegalStateException("Invalid saved server identity");
        Path saved=options.state().resolve("reports").resolve(instance).resolve(id+".json");
        if(Files.isRegularFile(saved)) {
            Map<String,Object> report=Json.object(Json.read(Files.readAllBytes(saved)));
            if(!id.equals(report.get("execution")))throw new IllegalStateException("Saved report identity changed");
            report.put("outcome","ok");return report;
        }
        live(state);
        return request(address(state),"GET","/v1/reports/"+id,null);
    }
}
