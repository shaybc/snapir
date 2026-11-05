package il.co.dcd.fixtures.jdbc;

import java.lang.reflect.*;
import java.sql.*;
import java.util.*;

/** Prepared/callable statements buffer bindings and submit complete indexed executions. */
final class StatementHandler implements InvocationHandler {
    private final ConnectionHandler owner;
    private final Connection connection;
    private final String sql;
    private final boolean callable;
    private final Map<Integer,Object> parameters=new TreeMap<>();
    private final Map<Integer,Integer> outputs=new TreeMap<>();
    private final List<ResultSet> cursors=new ArrayList<>();
    private Map<String,Object> executed;
    private ResultSet result;
    private boolean closed,wasNull;
    private int queryTimeout,fetchSize;
    private Statement proxy;
    private StatementHandler(ConnectionHandler owner,Connection connection,String sql,boolean callable) {
        this.owner=owner;this.connection=connection;this.sql=sql;this.callable=callable;
    }
    static Statement create(ConnectionHandler owner,Connection connection,String sql,boolean callable) {
        StatementHandler s=new StatementHandler(owner,connection,sql,callable);
        s.proxy=callable ? JdbcProxy.create(CallableStatement.class,s) : JdbcProxy.create(PreparedStatement.class,s);
        owner.statements.add(s);return s.proxy;
    }
    void closeLocal() {
        closed=true;for (ResultSet r : cursors) try { r.close(); } catch (SQLException ignored) { }
        owner.statements.remove(this);
    }
    private void execute() throws SQLException {
        for (ResultSet r : cursors) r.close();cursors.clear();result=null;executed=null;
        Map<String,Object> request=new LinkedHashMap<>();
        request.put("request",UUID.randomUUID().toString());request.put("kind",callable ? "callable" : "prepared");request.put("sql",sql);
        Map<String,Object> inputs=new TreeMap<>();parameters.forEach((k,v)->inputs.put(k.toString(),v));
        Map<String,Object> registrations=new TreeMap<>();outputs.forEach((k,v)->registrations.put(k.toString(),v));
        request.put("parameters",inputs);request.put("outputs",registrations);
        int previous=owner.transport.networkTimeout;
        try {
            if (queryTimeout>0) owner.transport.networkTimeout=previous>0 ? Math.min(previous,Math.multiplyExact(queryTimeout,1000)) : Math.multiplyExact(queryTimeout,1000);
            executed=owner.transport.call("POST",owner.path+"/execute",request);
        } finally { owner.transport.networkTimeout=previous; }
        if (!callable) { result=ResultHandler.create(executed,proxy,()->check(),owner::unsupported);cursors.add(result); }
    }
    private void check() throws SQLException { owner.check();if (closed) throw new SQLException("Fixture statement is closed"); }
    @Override public Object invoke(Object object,Method method,Object[] supplied) throws Throwable {
        Object[] a=supplied==null ? new Object[0] : supplied;String name=method.getName();
        if (JdbcProxy.common(method)) {
            try{return JdbcProxy.common(object,method,a);}
            catch(SQLException e){owner.unsupported(name);throw e;}
        }
        if (name.equals("close")) { closeLocal();return null; }
        if (name.equals("isClosed")) return closed || connection.isClosed();
        check();
        if (Set.of("setString","setInt","setLong","setBoolean","setObject","setBigDecimal","setDate","setTime","setTimestamp","setNull").contains(name)
                && a.length>=2 && a[0] instanceof Integer index) {
            if (index<1) throw new SQLException("Parameter indices start at one");
            if (a.length!=2) { owner.unsupported(name);throw JdbcProxy.unsupported(method); }
            parameters.put(index,name.equals("setNull") ? null : a[1]);return null;
        }
        switch (name) {
            case "clearParameters": parameters.clear();return null;
            case "registerOutParameter":
                if (callable && a.length==2 && a[0] instanceof Integer i && a[1] instanceof Integer t && i>0) { outputs.put(i,t);return null; }
                break;
            case "execute", "executeQuery":
                if (a.length!=0 || (callable && name.equals("executeQuery"))) break;
                execute();return name.equals("executeQuery") ? result : !callable;
            case "getResultSet": return result;
            case "getUpdateCount": return -1;
            case "getLargeUpdateCount": return -1L;
            case "getConnection": return connection;
            case "getString", "getObject":
                if (!callable || a.length!=1 || !(a[0] instanceof Integer index)) break;
                if (executed==null) throw new SQLException("Callable output read before execution");
                if(!il.co.dcd.fixtures.protocol.Json.object(executed.getOrDefault("out_parameters",Map.of())).containsKey(index.toString()))throw new SQLException("Callable output is not registered");
                Map<String,Object> output=il.co.dcd.fixtures.protocol.Json.object(
                    il.co.dcd.fixtures.protocol.Json.object(executed.get("out_parameters")).get(index.toString()));
                if (output.containsKey("rows")) {
                    if (!name.equals("getObject")) throw new SQLException("Cursor requires getObject");
                    ResultSet cursor=ResultHandler.create(output,proxy,()->check(),owner::unsupported);cursors.add(cursor);wasNull=false;return cursor;
                }
                Object value=output.get("value");wasNull=value==null;
                return name.equals("getString") && value!=null ? value.toString() : value;
            case "wasNull": return wasNull;
            case "setQueryTimeout": if ((Integer)a[0]<0) throw new SQLException("Negative query timeout");queryTimeout=(Integer)a[0];return null;
            case "getQueryTimeout": return queryTimeout;
            case "setFetchSize": if ((Integer)a[0]<0) throw new SQLException("Negative fetch size");fetchSize=(Integer)a[0];return null;
            case "getFetchSize": return fetchSize;
            case "getFetchDirection": return ResultSet.FETCH_FORWARD;
            case "setFetchDirection": if ((Integer)a[0]==ResultSet.FETCH_FORWARD) return null;break;
            case "getResultSetType": return ResultSet.TYPE_FORWARD_ONLY;
            case "getResultSetConcurrency": return ResultSet.CONCUR_READ_ONLY;
            case "getMaxRows": return 0;
            case "setMaxRows": if ((Integer)a[0]==0) return null;break;
            case "getWarnings": return null;
            case "clearWarnings": return null;
        }
        owner.unsupported(name);throw JdbcProxy.unsupported(method);
    }
}
