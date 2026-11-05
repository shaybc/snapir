package il.co.dcd.fixtures.jdbc;

import il.co.dcd.fixtures.protocol.FixtureUrl;
import java.lang.reflect.*;
import java.sql.*;
import java.util.*;
import java.util.concurrent.Executor;

/** One physical fixture connection with isolated state and owned statements. */
final class ConnectionHandler implements InvocationHandler {
    final Transport transport;
    final String path;
    final Set<StatementHandler> statements=Collections.synchronizedSet(new HashSet<>());
    private boolean closed;
    private Connection proxy;
    private final String url;
    private ConnectionHandler(FixtureUrl url,Properties properties) throws SQLException {
        this.url=FixtureUrl.PREFIX+url.endpoint().toString().substring("http:".length())+"/"+url.scenario()
            +"?execution="+url.execution()+(url.resource()==null ? "" : "&resource="+url.resource());
        transport=new Transport(url.endpoint(),properties);
        Map<String,Object> request=new LinkedHashMap<>();
        request.put("protocol",1);request.put("scenario",url.scenario());request.put("resource",url.resource());request.put("execution",url.execution());
        try {
            Map<String,Object> opened=transport.call("POST","/v1/connections",request);
            if (!Integer.valueOf(1).equals(opened.get("protocol"))) throw new SQLException("Incompatible fixture protocol","08004");
            path="/v1/connections/"+opened.get("connection");
        }catch(SQLException e){transport.close();throw e;}
    }
    static Connection open(FixtureUrl url,Properties properties) throws SQLException {
        ConnectionHandler handler=new ConnectionHandler(url,properties);
        handler.proxy=JdbcProxy.create(Connection.class,handler);return handler.proxy;
    }
    void check() throws SQLException { if (closed) throw new SQLException("Fixture connection is closed","08003"); }
    Map<String,Object> state() throws SQLException { check();return transport.call("GET",path+"/state",null); }
    void unsupported(String method) {
        try { transport.call("POST",path+"/diagnostic",Map.of("code","CAPABILITY_UNSUPPORTED","method",method)); } catch (SQLException ignored) { }
    }
    void set(String key,Object value) throws SQLException {
        Map<String,Object> update=new HashMap<>();update.put(key,value);transport.call("PUT",path+"/state",update);
    }
    @Override public Object invoke(Object object,Method method,Object[] supplied) throws Throwable {
        Object[] a=supplied==null ? new Object[0] : supplied;
        if (JdbcProxy.common(method)) {
            try{return JdbcProxy.common(object,method,a);}
            catch(SQLException e){unsupported(method.getName());throw e;}
        }
        String name=method.getName();
        if (name.equals("close") || name.equals("abort")) {
            if (closed) return null;
            try { transport.call("DELETE",path,null); }
            finally { closed=true;for (StatementHandler s : List.copyOf(statements)) s.closeLocal();transport.close(); }
            return null;
        }
        if (name.equals("isClosed")) return closed;
        if (name.equals("isValid")) {
            if ((Integer)a[0]<0) throw new SQLException("Negative validity timeout");
            if (closed) return false;
            int prior=transport.networkTimeout;
            try { if ((Integer)a[0]>0) transport.networkTimeout=Math.multiplyExact((Integer)a[0],1000);state();return true; }
            catch (SQLException e) { return false; } finally { transport.networkTimeout=prior; }
        }
        check();
        switch (name) {
            case "prepareStatement", "prepareCall":
                if (a.length!=1) break;
                return StatementHandler.create(this,proxy,(String)a[0],name.equals("prepareCall"));
            case "getAutoCommit": return state().get("autoCommit");
            case "isReadOnly": return state().get("readOnly");
            case "getTransactionIsolation": return ((Number)state().get("transactionIsolation")).intValue();
            case "getCatalog": return state().get("catalog");
            case "getSchema": return state().get("schema");
            case "setAutoCommit": set("autoCommit",a[0]);return null;
            case "setReadOnly": set("readOnly",a[0]);return null;
            case "setTransactionIsolation": set("transactionIsolation",a[0]);return null;
            case "setCatalog": set("catalog",a[0]);return null;
            case "setSchema": set("schema",a[0]);return null;
            case "setNetworkTimeout":
                if (a[0]==null || (Integer)a[1]<0) throw new SQLException("Invalid network timeout");
                set("networkTimeout",a[1]);transport.networkTimeout=(Integer)a[1];return null;
            case "getNetworkTimeout": return ((Number)state().get("networkTimeout")).intValue();
            case "commit", "rollback":
                if (a.length!=0) break;
                transport.call("POST",path+"/transaction",Map.of("action",name));return null;
            case "getWarnings": return null;
            case "clearWarnings": return null;
            case "nativeSQL": return a[0];
            case "getMetaData": return DriverMetadata.create(proxy,url,this::unsupported);
        }
        unsupported(name);throw JdbcProxy.unsupported(method);
    }
}
