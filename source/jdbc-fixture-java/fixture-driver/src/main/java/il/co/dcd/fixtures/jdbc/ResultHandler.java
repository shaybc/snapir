package il.co.dcd.fixtures.jdbc;

import java.lang.reflect.*;
import java.math.BigDecimal;
import java.sql.*;
import java.util.*;
import java.util.function.Consumer;
import il.co.dcd.fixtures.replay.Replay;

/** Bounded forward-only results retain exact column names and explicit JDBC null state. */
final class ResultHandler implements InvocationHandler {
    @FunctionalInterface interface OwnerCheck { void check() throws SQLException; }
    private final List<String> columns;
    private final List<List<Object>> rows;
    private final Statement statement;
    private final OwnerCheck owner;
    private final Consumer<String> diagnostic;
    private int row=-1;
    private boolean closed,wasNull;
    @SuppressWarnings("unchecked") private ResultHandler(Map<String,Object> data,Statement statement,OwnerCheck owner,Consumer<String> diagnostic) {
        columns=(List<String>)data.getOrDefault("columns",List.of());rows=(List<List<Object>>)data.getOrDefault("rows",List.of());
        this.statement=statement;this.owner=owner;this.diagnostic=diagnostic;
    }
    static ResultSet create(Map<String,Object> data,Statement statement,OwnerCheck owner,Consumer<String> diagnostic) { return JdbcProxy.create(ResultSet.class,new ResultHandler(data,statement,owner,diagnostic)); }
    @Override public Object invoke(Object object,Method method,Object[] supplied) throws Throwable {
        Object[] a=supplied==null ? new Object[0] : supplied;String name=method.getName();
        if (JdbcProxy.common(method)) {
            try{return JdbcProxy.common(object,method,a);}
            catch(SQLException e){diagnostic.accept(name);throw e;}
        }
        if (name.equals("close")) { closed=true;return null; }
        if (name.equals("isClosed")) return closed;
        owner.check();if (closed) throw new SQLException("Fixture result is closed");
        switch (name) {
            case "next": return ++row<rows.size();
            case "wasNull": return wasNull;
            case "getStatement": return statement;
            case "getRow": return row>=0 && row<rows.size() ? row+1 : 0;
            case "getType": return ResultSet.TYPE_FORWARD_ONLY;
            case "getConcurrency": return ResultSet.CONCUR_READ_ONLY;
            case "findColumn": { int i=columns.indexOf(a[0]);if (i<0) throw new SQLException("Unknown fixture column");return i+1; }
        }
        if (Set.of("getString","getObject","getInt","getLong","getBoolean","getBigDecimal","getDate","getTime","getTimestamp","getBytes").contains(name) && a.length==1) {
            int index=a[0] instanceof Integer i ? i-1 : columns.indexOf(a[0]);
            if (row<0 || row>=rows.size() || index<0 || index>=columns.size()) throw new SQLException("Fixture cursor or column unavailable");
            Object value=rows.get(row).get(index);wasNull=value==null;
            if(Set.of("getString","getObject","getInt","getLong","getBoolean","getBigDecimal").contains(name)) {
                try{return Replay.column(value,name);}catch(RuntimeException e){diagnostic.accept(name);throw new SQLException("Fixture value cannot satisfy getter",e);}
            }
            try { return switch (name) {
                case "getDate" -> value==null ? null : new java.sql.Date(((java.util.Date)value).getTime());
                case "getTime" -> value==null ? null : new java.sql.Time(((java.util.Date)value).getTime());
                case "getTimestamp" -> value==null ? null : value instanceof Timestamp ? value : new Timestamp(((java.util.Date)value).getTime());
                case "getBytes" -> value==null ? null : ((byte[])value).clone();
                default -> value;
            }; } catch (RuntimeException e) { throw new SQLException("Fixture value cannot satisfy getter",e); }
        }
        diagnostic.accept(name);throw JdbcProxy.unsupported(method);
    }
}
