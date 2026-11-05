package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.Json;
import il.co.dcd.fixtures.replay.Replay;
import java.sql.Connection;
import java.util.*;

/** One connection's JDBC state; immutable fixture data is not a transaction engine. */
final class FixtureSession {
    final String id=UUID.randomUUID().toString(),execution;
    final List<Map<String,Object>> queries;
    final Map<String,Object> state=new LinkedHashMap<>();
    long touched=System.nanoTime();boolean closed;
    FixtureSession(String execution,List<Map<String,Object>> queries) {
        this.execution=execution;this.queries=queries;
        state.put("autoCommit",true);state.put("readOnly",false);state.put("transactionIsolation",Connection.TRANSACTION_READ_COMMITTED);
        state.put("catalog",null);state.put("schema",null);state.put("networkTimeout",0);
    }
    void update(Map<String,Object> update) {
        Json.keys(update,"autoCommit","readOnly","transactionIsolation","catalog","schema","networkTimeout");
        for (var entry : update.entrySet()) {
            String key=entry.getKey();Object value=entry.getValue();
            boolean valid=switch (key) {
                case "autoCommit","readOnly" -> value instanceof Boolean;
                case "schema","catalog" -> value==null || value instanceof String;
                case "networkTimeout" -> value instanceof Integer n && n>=0;
                case "transactionIsolation" -> value instanceof Integer n && Set.of(0,1,2,4,8).contains(n);
                default -> false;
            };
            if (!valid) throw new IllegalArgumentException("Invalid JDBC connection state");
        }
        state.putAll(update);
    }
    Map<String,Object> execute(Map<String,Object> request) {
        Json.keys(request,"request","kind","sql","parameters","outputs");
        if (!(request.get("request") instanceof String) || !(request.get("sql") instanceof String sql)) throw new IllegalArgumentException("Execution requires request identity and SQL");
        String kind=(String)request.get("kind");
        if (!Set.of("prepared","callable").contains(kind)) return failure("CAPABILITY_UNSUPPORTED");
        Map<String,Object> parameters=Json.object(request.get("parameters")),outputs=Json.object(request.get("outputs"));
        TreeMap<Integer,Object> ordered=new TreeMap<>();
        for (var entry : parameters.entrySet()) { int index=index(entry.getKey());ordered.put(index,entry.getValue()); }
        Set<Integer> registered=new HashSet<>();
        for (var entry : outputs.entrySet()) {
            registered.add(index(entry.getKey()));if (!(entry.getValue() instanceof Integer)) throw new IllegalArgumentException("Output JDBC type must be an integer");
        }
        Set<Integer> indices=new HashSet<>(ordered.keySet());indices.addAll(registered);
        for (int i=1;i<=indices.size();i++) if (!indices.contains(i)) return failure("FIXTURE_MISS");
        Map<String,Object> match=Replay.find(queries,sql,new ArrayList<>(ordered.values()));
        if (match==null) return failure("FIXTURE_MISS");
        Map<String,Object> expected=Json.object(match.getOrDefault("out_parameters",Map.of()));
        if ((kind.equals("prepared") && !expected.isEmpty()) || !expected.keySet().equals(outputs.keySet())) return failure("FIXTURE_MISS");
        for (var entry : expected.entrySet()) if (!Objects.equals(Json.object(entry.getValue()).get("sql_type"),outputs.get(entry.getKey()))) return failure("FIXTURE_MISS");
        if (match.get("exception") instanceof Map<?,?> error) return new LinkedHashMap<>(Map.of("outcome","sql_exception","message",String.valueOf(error.get("message"))));
        Map<String,Object> result=new LinkedHashMap<>(match);result.remove("sql");result.remove("parameters");result.put("outcome","ok");return result;
    }
    private static int index(String value) {
        if (!value.matches("[1-9][0-9]{0,5}")) throw new IllegalArgumentException("Invalid JDBC parameter index");return Integer.parseInt(value);
    }
    static Map<String,Object> failure(String code) { return new LinkedHashMap<>(Map.of("outcome","error","code",code)); }
}
