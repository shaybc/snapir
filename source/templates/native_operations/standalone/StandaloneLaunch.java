// Demo belongs to external launch tooling. The Java runner receives only normal JDBC configuration.
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

public final class StandaloneLaunch {
    public static void main(String[] args) {
        int status;
        try { status = launch(args); }
        catch (Exception error) {
            // Do not echo arbitrary request/configuration data or JDBC exception messages.
            System.err.println("External launcher failed ("+error.getClass().getSimpleName()+"). Inspect the demo binding, tool identities and server.log.");
            status = 1;
        }
        if (status!=0) System.exit(status);
    }
    static int launch(String[] args) throws Exception {
        if (args.length<1) throw new IllegalArgumentException("Missing operation binding");
        List<String> forwarded = new ArrayList<>(Arrays.asList(args));
        boolean demo = forwarded.remove("--demo"), stop = forwarded.remove("--demo-stop");
        if (forwarded.contains("--demo") || forwarded.contains("--demo-stop"))
            throw new IllegalArgumentException("Duplicate demo option");
        if (!demo && !stop) return invoke(forwarded,null,0);
        if (forwarded.contains("--config") || forwarded.contains("--database")) {
            System.err.println("Demo cannot be combined with --config or --database overrides.");
            throw new IllegalArgumentException("Demo conflicts with explicit config/database overrides");
        }
        DemoBinding binding = new DemoBinding(Path.of(args[0]),!stop);
        Files.createDirectories(binding.state);
        try (FileChannel channel=FileChannel.open(binding.state.resolve("launcher.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);
             FileLock lock=channel.tryLock()) {
            if (lock==null) throw new IllegalStateException("Another demo invocation owns this launcher");
            if (stop) { DemoServerProcess.command(binding,"stop"); return 0; }
            if (forwarded.size()!=2) throw new IllegalArgumentException("Demo requires exactly one XML request path");
            boolean owned=false;
            String execution="standalone-"+UUID.randomUUID();
            Path temporary=null;
            int status=1;
            ObjectNode report=DemoBinding.JSON.createObjectNode();
            report.put("status","execution_failed");report.put("execution",execution);
            try {
                var started=DemoServerProcess.command(binding,"ensure");
                owned=!started.path("reused").asBoolean(true);
                temporary=Files.createTempFile(binding.state,"runtime-",".json");
                String url=binding.text("jdbc_url");
                url += (url.contains("?") ? "&" : "?")+"execution="+execution;
                ObjectNode config=DemoBinding.JSON.createObjectNode();
                Path originalConfig=bindingProjectConfig(Path.of(args[0]));
                if(Files.isRegularFile(originalConfig)) {
                    var original=DemoBinding.JSON.readTree(originalConfig.toFile());
                    if(original.has("service_urls"))config.set("service_urls",original.path("service_urls"));
                }
                ObjectNode db=config.putObject("databases").putObject(binding.text("database"));
                db.put("jdbc_url",url);db.put("driver_class",binding.text("driver_class"));
                db.put("user","");db.put("password","");
                DemoBinding.JSON.writeValue(temporary.toFile(),config);
                forwarded.addAll(List.of("--config",temporary.toString(),"--database",binding.text("database")));
                status=invoke(forwarded,binding.driver,binding.settings.path("invocation_timeout_ms").asInt(120000));
                var replay=DemoServerProcess.command(binding,"report","--execution",execution);
                report.set("replay",replay);
                if (replay.path("failed").asBoolean(true)) status=1;
                report.put("status",status==0 ? "completed" : "execution_failed");
                report.put("notice","Smoke invocation only; no equivalence or saved expected-response verification.");
                return status;
            } finally {
                try {
                    if (temporary!=null) Files.deleteIfExists(temporary);
                } catch (Exception cleanup) {
                    report.put("status","execution_failed");throw cleanup;
                } finally {
                  try {
                    if (owned && binding.settings.path("stop_when_finished").asBoolean(true))
                        DemoServerProcess.command(binding,"stop");
                  } catch (Exception cleanup) {
                    report.put("status","execution_failed");throw cleanup;
                  } finally {
                    DemoBinding.JSON.writerWithDefaultPrettyPrinter().writeValue(binding.state.resolve("last-run.json").toFile(),report);
                    System.err.println("Demo report: "+binding.state.resolve("last-run.json"));
                  }
                }
            }
        }
    }
    static Path bindingProjectConfig(Path binding) throws Exception {
        var operation=DemoBinding.JSON.readTree(binding.toFile());
        return binding.toAbsolutePath().getParent().resolve(operation.path("runtime_config").asText()).normalize();
    }
    static int invoke(List<String> args,Path driver,int timeoutMs) throws Exception {
        String cp=System.getProperty("java.class.path");
        if (driver!=null) cp=driver+java.io.File.pathSeparator+cp;
        List<String> command=new ArrayList<>(List.of(DemoServerProcess.javaCommand(),"-Dfile.encoding=UTF-8",
            "-cp",cp,"StandaloneOperationRunner"));command.addAll(args);
        Process process=new ProcessBuilder(command).inheritIO().start();
        if (timeoutMs>0 && !process.waitFor(timeoutMs,TimeUnit.MILLISECONDS)) {
            process.destroyForcibly();process.waitFor(5,TimeUnit.SECONDS);
            throw new IllegalStateException("Operation demo timed out");
        }
        return process.waitFor();
    }
}
