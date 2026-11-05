package il.co.dcd.fixtures.server;

import com.sun.net.httpserver.*;
import il.co.dcd.fixtures.protocol.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

/** Network boundary for fixture JDBC only; never executes SQL or opens a real database. */
public final class FixtureServer implements AutoCloseable {
    private final FixtureCatalogue catalogue;
    private final HttpServer server;
    private final ExecutorService workers=new ThreadPoolExecutor(8,8,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(128));
    private final ScheduledExecutorService expiry=Executors.newSingleThreadScheduledExecutor();
    private final Map<String,FixtureSession> sessions=new ConcurrentHashMap<>();
    private final ExecutionJournal journal;
    private final String ownerToken;
    private final boolean debug;
    public final String instance=UUID.randomUUID().toString();
    private final long processId=ProcessHandle.current().pid();
    private final String processStart=ProcessHandle.current().info().startInstant().orElseThrow().toString();
    private final String artifactHash;
    private final CountDownLatch stopped=new CountDownLatch(1);
    public FixtureServer(FixtureCatalogue catalogue,InetSocketAddress address,String ownerToken,boolean debug,String artifactHash) throws IOException {
        this(catalogue,address,ownerToken,debug,artifactHash,null);
    }
    public FixtureServer(FixtureCatalogue catalogue,InetSocketAddress address,String ownerToken,boolean debug,String artifactHash,java.nio.file.Path reportDirectory) throws IOException {
        this.catalogue=catalogue;this.ownerToken=ownerToken;this.debug=debug;this.artifactHash=artifactHash;
        journal=new ExecutionJournal(reportDirectory==null ? null : reportDirectory.resolve(instance));
        server=HttpServer.create(address,64);server.createContext("/v1/",this::handle);server.setExecutor(workers);
    }
    public void start() {
        server.start();expiry.scheduleAtFixedRate(()->sessions.values().removeIf(s->{ synchronized(s) { return s.closed || System.nanoTime()-s.touched>TimeUnit.MINUTES.toNanos(10); } }),30,30,TimeUnit.SECONDS);
    }
    public int port() { return server.getAddress().getPort(); }
    public Map<String,Object> health() {
        return Map.of("outcome","ok","protocol",1,"tool_version","1.0.0","server",instance,"catalogue_hash",catalogue.hash,"artifact_hash",artifactHash,"ready",true,
            "pid",processId,"process_start",processStart);
    }
    private void handle(HttpExchange exchange) throws IOException {
        ScheduledFuture<?> deadline=expiry.schedule(exchange::close,15,TimeUnit.SECONDS);
        Map<String,Object> response;int status=200;
        try {
            byte[] bytes=exchange.getRequestBody().readNBytes(Json.MAX_BYTES+1);
            if (bytes.length>Json.MAX_BYTES) throw new IllegalArgumentException("Request size limit");
            Map<String,Object> request=bytes.length==0 ? Map.of() : Json.object(Values.decode(Json.read(bytes)));
            response=route(exchange.getRequestMethod(),exchange.getRequestURI().getPath(),request);
        } catch (IllegalArgumentException | ClassCastException | NullPointerException e) { response=FixtureSession.failure("INVALID_REQUEST");status=400; }
        catch (Exception e) { response=FixtureSession.failure("SERVER_FAILURE");status=500; }
        byte[] output=Json.bytes(Values.encode(response));
        if (output.length>Json.MAX_BYTES) { output=Json.bytes(FixtureSession.failure("RESPONSE_SIZE_LIMIT"));status=413; }
        exchange.getResponseHeaders().set("Content-Type","application/json");exchange.sendResponseHeaders(status,output.length);
        try (OutputStream stream=exchange.getResponseBody()) { stream.write(output); }
        finally { deadline.cancel(false);exchange.close(); }
    }
    private Map<String,Object> route(String method,String path,Map<String,Object> request) throws IOException {
        if (path.equals("/v1/health") && method.equals("GET")) return health();
        if (path.equals("/v1/shutdown") && method.equals("POST")) {
            if (ownerToken==null || !java.security.MessageDigest.isEqual(ownerToken.getBytes(java.nio.charset.StandardCharsets.UTF_8),String.valueOf(request.get("token")).getBytes(java.nio.charset.StandardCharsets.UTF_8))) return FixtureSession.failure("NOT_OWNER");
            Thread.ofPlatform().start(()->{try {Thread.sleep(100);}catch(InterruptedException ignored){}close();});return Map.of("outcome","ok");
        }
        if (path.startsWith("/v1/reports/") && method.equals("GET")) {
            Map<String,Object> report=journal.report(path.substring("/v1/reports/".length()));report.put("outcome","ok");return report;
        }
        if (path.equals("/v1/connections") && method.equals("POST")) {
            Json.keys(request,"protocol","scenario","resource","execution");
            if (!Integer.valueOf(1).equals(request.get("protocol"))) return FixtureSession.failure("PROTOCOL_MISMATCH");
            String execution=(String)request.get("execution");
            if (execution==null || !execution.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")) throw new IllegalArgumentException("Invalid execution ID");
            synchronized (sessions) {
                if (sessions.size()>=64) return FixtureSession.failure("CONNECTION_LIMIT");
                FixtureSession s=new FixtureSession(execution,catalogue.resource((String)request.get("scenario"),(String)request.get("resource")));
                journal.record(execution,s.id,"open","ok",null,null);sessions.put(s.id,s);
                return Map.of("outcome","ok","connection",s.id,"protocol",1,"catalogue_hash",catalogue.hash,"server",instance);
            }
        }
        String[] parts=path.split("/");
        if (parts.length<4 || !parts[2].equals("connections")) return FixtureSession.failure("UNKNOWN_ENDPOINT");
        FixtureSession s=sessions.get(parts[3]);
        if (s==null) return method.equals("DELETE") && parts.length==4 ? Map.of("outcome","ok") : FixtureSession.failure("CONNECTION_CLOSED");
        synchronized (s) {
            s.touched=System.nanoTime();
            if (s.closed) return FixtureSession.failure("CONNECTION_CLOSED");
            if (parts.length==4 && method.equals("DELETE")) {
                s.closed=true;sessions.remove(s.id);journal.record(s.execution,s.id,"close","ok",null,null);return Map.of("outcome","ok");
            }
            if (parts.length!=5) return FixtureSession.failure("UNKNOWN_ENDPOINT");
            Map<String,Object> response;
            switch (parts[4]) {
                case "state":
                    if (method.equals("PUT")) s.update(request);else if (!method.equals("GET")) return FixtureSession.failure("UNKNOWN_ENDPOINT");
                    response=new LinkedHashMap<>(s.state);response.put("outcome","ok");return response;
                case "execute":
                    if (!method.equals("POST")) return FixtureSession.failure("UNKNOWN_ENDPOINT");
                    try { response=s.execute(request); }
                    catch (RuntimeException e) { response=FixtureSession.failure("INVALID_REQUEST"); }
                    if (Json.bytes(Values.encode(response)).length>Json.MAX_BYTES) response=FixtureSession.failure("RESPONSE_SIZE_LIMIT");
                    journal.record(s.execution,s.id,"execute",(String)response.get("outcome"),(String)response.get("code"),null);
                    if (debug) System.err.println(Json.canonical(Values.encode(Map.of("connection",s.id,"execution",s.execution,"request",request,"response",response))));
                    return response;
                case "diagnostic":
                    if (!method.equals("POST")) return FixtureSession.failure("UNKNOWN_ENDPOINT");
                    Json.keys(request,"code","method");journal.record(s.execution,s.id,"capability","error","CAPABILITY_UNSUPPORTED",(String)request.get("method"));return Map.of("outcome","ok");
                case "transaction":
                    if (!method.equals("POST") || !Set.of("commit","rollback").contains(request.get("action"))) return FixtureSession.failure("INVALID_REQUEST");
                    journal.record(s.execution,s.id,(String)request.get("action"),"ok",null,null);return Map.of("outcome","ok");
                default: return FixtureSession.failure("UNKNOWN_ENDPOINT");
            }
        }
    }
    public void await() throws InterruptedException { stopped.await(); }
    @Override public void close() { server.stop(0);workers.shutdownNow();expiry.shutdownNow();sessions.clear();stopped.countDown(); }
}
