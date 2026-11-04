package il.co.dcd.verification.fixtures;

import java.lang.reflect.*;
import java.sql.*;
import java.util.*;
import il.co.dcd.verification.harness.BoundaryRuntime;

/** A bounded JDBC capability, backed only by explicit SQL/parameter/result fixtures. */
public final class JdbcFixtureProvider implements InvocationHandler {
    private final String kind;
    private final Map<String, Object> specification;
    private final List<Map<String, Object>> events;
    private final String sql;
    private final String resource;
    private final Map<Integer, Object> parameters = new TreeMap<>();
    private final Map<Integer, Integer> outputTypes = new TreeMap<>();
    private Map<String, Object> executed;
    private int row = -1;
    private boolean closed, wasNull, autoCommit = true;
    private JdbcFixtureProvider(String kind, Map<String, Object> specification, List<Map<String, Object>> events, String sql, String resource) {
        this.kind = kind; this.specification = specification; this.events = events; this.sql = sql; this.resource = resource;
    }
    public static Connection connection(Map<String, Object> specification, List<Map<String, Object>> events) {
        return connection(specification,events,"database");
    }
    public static Connection connection(Map<String, Object> specification, List<Map<String, Object>> events, String resource) {
        return (Connection) proxy(Connection.class, new JdbcFixtureProvider("connection", specification, events, null, resource));
    }
    private static Object proxy(Class<?> type, JdbcFixtureProvider handler) {
        return Proxy.newProxyInstance(JdbcFixtureProvider.class.getClassLoader(), new Class<?>[]{type}, handler);
    }
    static boolean owned(Object object) {
        return object != null && Proxy.isProxyClass(object.getClass()) && Proxy.getInvocationHandler(object) instanceof JdbcFixtureProvider;
    }
    @SuppressWarnings("unchecked") public Object invoke(Object receiver, Method method, Object[] args) throws Throwable {
        Object[] values = args == null ? new Object[0] : args;
        String name = method.getName();
        if (method.getDeclaringClass() == Object.class) return switch (name) {
            case "toString" -> "FixtureJDBC:" + kind;
            case "hashCode" -> System.identityHashCode(receiver);
            case "equals" -> receiver == values[0];
            default -> throw new BoundaryRuntime.Incomplete("Unsupported JDBC object operation");
        };
        if (name.equals("close")) { closed = true; event("close",List.of()); return null; }
        if (name.equals("isClosed")) return closed;
        if (closed) throw new SQLException("Fixture JDBC resource is closed");
        if (kind.equals("connection")) {
            if (name.equals("prepareStatement") && values.length == 1 && values[0] instanceof String query)
                return proxy(PreparedStatement.class, new JdbcFixtureProvider("statement", specification, events, query, resource));
            if (name.equals("prepareCall") && values.length == 1 && values[0] instanceof String query)
                return proxy(CallableStatement.class, new JdbcFixtureProvider("callable", specification, events, query, resource));
            if (name.equals("getAutoCommit")) return autoCommit;
            if (name.equals("setAutoCommit")) { autoCommit = (Boolean) values[0]; event(name, List.of(autoCommit)); return null; }
            if (name.equals("commit") || name.equals("rollback")) { event(name, List.of()); return null; }
        } else if (kind.equals("statement") || kind.equals("callable")) {
            if (Set.of("setString", "setInt", "setLong", "setBoolean", "setObject", "setBigDecimal").contains(name) && values.length == 2) {
                parameters.put((Integer) values[0], values[1]); return null;
            }
            if (name.equals("setNull") && values.length >= 2) { parameters.put((Integer) values[0], null); return null; }
            if (name.equals("clearParameters")) { parameters.clear(); return null; }
            if (kind.equals("callable") && name.equals("registerOutParameter") && values.length == 2
                    && values[0] instanceof Integer index && values[1] instanceof Integer type) {
                outputTypes.put(index, type); return null;
            }
            if (kind.equals("callable") && name.equals("execute") && values.length == 0) {
                List<Object> ordered = new ArrayList<>(parameters.values());
                event("call", ordered);
                for (Map<String, Object> query : (List<Map<String, Object>>) specification.get("queries")) {
                    if (!sql.equals(query.get("sql")) || !same(ordered, (List<?>)query.get("parameters"))) continue;
                    Map<String, Map<String, Object>> outputs = (Map<String, Map<String, Object>>) query.getOrDefault("out_parameters", Map.of());
                    if (outputs.size() != outputTypes.size() || outputTypes.entrySet().stream().anyMatch(entry ->
                            !outputs.containsKey(entry.getKey().toString()) ||
                            ((Number) outputs.get(entry.getKey().toString()).get("sql_type")).intValue() != entry.getValue()))
                        throw new BoundaryRuntime.Incomplete("Callable output registrations do not match fixture");
                    if (query.get("exception") instanceof Map<?, ?> failure) throw new SQLException(String.valueOf(failure.get("message")));
                    executed = query; return false;
                }
                throw new BoundaryRuntime.Incomplete("No fixture call matches SQL and parameters: " + sql);
            }
            if (kind.equals("callable") && Set.of("getString", "getObject").contains(name)
                    && values.length == 1 && values[0] instanceof Integer index) {
                if (executed == null) throw new BoundaryRuntime.Incomplete("Callable output read before execution");
                Map<String, Object> output = ((Map<String, Map<String, Object>>) executed.get("out_parameters")).get(index.toString());
                if (output == null) throw new BoundaryRuntime.Incomplete("Callable output parameter is not declared");
                if (output.containsKey("rows")) {
                    if (!name.equals("getObject")) throw new BoundaryRuntime.Incomplete("Cursor output requires getObject");
                    wasNull = false;
                    return proxy(ResultSet.class, new JdbcFixtureProvider("result", output, events, sql, resource));
                }
                Object value = output.get("value"); wasNull = value == null;
                return name.equals("getString") && value != null ? String.valueOf(value) : value;
            }
            if (kind.equals("callable") && name.equals("wasNull")) return wasNull;
            if (name.equals("executeQuery") && values.length == 0) {
                List<Object> ordered = new ArrayList<>();
                for (int i = 1; i <= parameters.size(); i++) {
                    if (!parameters.containsKey(i)) throw new BoundaryRuntime.Incomplete("Missing JDBC parameter " + i);
                    ordered.add(parameters.get(i));
                }
                event("query", ordered);
                for (Map<String, Object> query : (List<Map<String, Object>>) specification.get("queries")) {
                    if (!sql.equals(query.get("sql")) || !same(ordered, (List<?>)query.get("parameters"))) continue;
                    if (query.get("exception") instanceof Map<?, ?> failure) throw new SQLException(String.valueOf(failure.get("message")));
                    return proxy(ResultSet.class, new JdbcFixtureProvider("result", query, events, sql, resource));
                }
                throw new BoundaryRuntime.Incomplete("No fixture query matches SQL and parameters: " + sql);
            }
        } else if (kind.equals("result")) {
            List<List<Object>> rows = (List<List<Object>>) specification.getOrDefault("rows", List.of());
            List<String> columns = (List<String>) specification.getOrDefault("columns", List.of());
            if (name.equals("next")) return ++row < rows.size();
            if (name.equals("wasNull")) return wasNull;
            if (Set.of("getString", "getObject", "getInt", "getLong", "getBoolean", "getBigDecimal").contains(name) && values.length == 1) {
                int column = values[0] instanceof Number n ? n.intValue()-1 : columns.indexOf(values[0]);
                if (row < 0 || row >= rows.size() || column < 0 || column >= columns.size()) throw new BoundaryRuntime.Incomplete("Fixture result cursor/column unavailable");
                Object value = rows.get(row).get(column); wasNull = value == null;
                try { return switch (name) {
                    case "getString" -> value == null ? null : String.valueOf(value);
                    case "getInt" -> value == null ? 0 : new java.math.BigDecimal(value.toString()).intValueExact();
                    case "getLong" -> value == null ? 0L : new java.math.BigDecimal(value.toString()).longValueExact();
                    case "getBoolean" -> value == null ? false : (Boolean) value;
                    case "getBigDecimal" -> value == null ? null : new java.math.BigDecimal(value.toString());
                    default -> value;
                }; } catch (ClassCastException | IllegalArgumentException | ArithmeticException unsupportedValue) {
                    throw new BoundaryRuntime.Incomplete("Unsupported fixture JDBC column value for " + name);
                }
            }
        }
        throw new BoundaryRuntime.Incomplete("Unsupported fixture JDBC capability: " + kind + "." + name);
    }
    private void event(String operation, List<?> arguments) {
        Map<String, Object> event = new LinkedHashMap<>(); event.put("operation", operation); event.put("sql", sql); event.put("arguments", arguments); event.put("resource",resource); event.put("resource_kind",kind); events.add(event);
    }
    private static boolean same(List<?> left,List<?> right) {
        if (left.size()!=right.size()) return false;
        for(int i=0;i<left.size();i++) {
            Object a=left.get(i),b=right.get(i);
            if(a instanceof Number && b instanceof Number) { if(new java.math.BigDecimal(a.toString()).compareTo(new java.math.BigDecimal(b.toString()))!=0)return false; }
            else if(!Objects.equals(a,b)) return false;
        }
        return true;
    }
}
