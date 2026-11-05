package il.co.dcd.fixtures.server;

import java.util.*;
import java.nio.file.*;
import il.co.dcd.fixtures.protocol.Json;

/** Bounded sticky diagnostics survive application handling of fixture infrastructure errors. */
final class ExecutionJournal {
    private final Map<String,Map<String,Object>> executions=new LinkedHashMap<>();
    private int eventCount;
    private final Path directory;
    ExecutionJournal(Path directory) { this.directory=directory; }
    private void persist(String execution,Map<String,Object> report) {
        if(directory==null)return;
        try {
            Files.createDirectories(directory);Path temporary=Files.createTempFile(directory,".report-",".json");
            try {Files.write(temporary,Json.bytes(report));Files.move(temporary,directory.resolve(execution+".json"),StandardCopyOption.REPLACE_EXISTING);}
            finally{Files.deleteIfExists(temporary);}
        }catch(java.io.IOException e){throw new IllegalStateException("Fixture report could not be saved",e);}
    }
    synchronized void record(String execution,String connection,String kind,String outcome,String code,String method) {
        Map<String,Object> report=executions.get(execution);
        if (report==null) {
            if (executions.size()>=1024) throw new IllegalStateException("Execution journal capacity exceeded");
            report=new LinkedHashMap<>();report.put("execution",execution);report.put("failed",false);report.put("events",new ArrayList<>());executions.put(execution,report);
        }
        boolean failed=!Set.of("ok","sql_exception").contains(outcome);
        if (failed) report.put("failed",true);
        if (++eventCount>10000) { report.put("failed",true);report.put("overflow",true);persist(execution,report);throw new IllegalStateException("Execution event capacity exceeded"); }
        Map<String,Object> event=new LinkedHashMap<>();event.put("connection",connection);event.put("operation",kind);event.put("outcome",outcome);event.put("code",code);
        if (method!=null) event.put("method",method);
        ((List<Object>)report.get("events")).add(event);
        persist(execution,report);
    }
    synchronized Map<String,Object> report(String execution) {
        if (!executions.containsKey(execution)) throw new IllegalArgumentException("Unknown execution");
        Map<String,Object> copy=new LinkedHashMap<>(executions.get(execution));
        copy.put("events",List.copyOf((List<?>)copy.get("events")));return copy;
    }
}
