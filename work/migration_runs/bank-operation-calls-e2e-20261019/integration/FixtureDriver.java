package validation;

import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.sql.*;
import java.util.*;
import java.util.logging.Logger;

/** Integration-only substitute for the demo's unavailable Oracle procedure and lookup table. */
public final class FixtureDriver implements Driver {
    static {
        try { DriverManager.registerDriver(new FixtureDriver()); }
        catch (SQLException exception) { throw new ExceptionInInitializerError(exception); }
    }

    @Override public boolean acceptsURL(String url) { return url != null && url.startsWith("jdbc:bank-fixture:"); }
    @Override public Connection connect(String url, Properties properties) {
        if (!acceptsURL(url)) return null;
        return (Connection) Proxy.newProxyInstance(getClass().getClassLoader(), new Class<?>[]{Connection.class},
            (proxy, method, args) -> switch (method.getName()) {
                case "prepareCall" -> statement(true, (String) args[0]);
                case "prepareStatement" -> statement(false, (String) args[0]);
                case "isValid", "getAutoCommit" -> true;
                case "isClosed", "isReadOnly", "isWrapperFor" -> false;
                case "getTransactionIsolation" -> Connection.TRANSACTION_READ_COMMITTED;
                case "toString" -> "BankIntegrationFixtureConnection";
                case "unwrap" -> proxy;
                default -> empty(method.getReturnType());
            });
    }

    private Object statement(boolean procedure, String sql) {
        Map<Integer,Object> inputs = new HashMap<>();
        return Proxy.newProxyInstance(getClass().getClassLoader(),
            new Class<?>[]{procedure ? CallableStatement.class : PreparedStatement.class}, (proxy, method, args) -> {
                String name = method.getName();
                if (name.startsWith("set") && args != null && args.length >= 2 && args[0] instanceof Integer index) {
                    inputs.put(index, args[1]); return null;
                }
                if (name.equals("execute") || name.equals("executeQuery")) {
                    String client = String.valueOf(inputs.get(1));
                    String log = System.getProperty("bank.fixture.log");
                    if (log != null) Files.writeString(Path.of(log), sql + " " + inputs + System.lineSeparator(),
                        StandardOpenOption.CREATE, StandardOpenOption.APPEND);
                    if (client.equals("DBERROR")) throw new SQLException("Intentional integration database failure");
                    if (name.equals("executeQuery")) return rows(procedure, client);
                    return true;
                }
                if (name.equals("getString")) return "MISSING".equals(inputs.get(1)) ? "NOT_FOUND" : "SUCCESS";
                if (name.equals("getObject") || name.equals("getResultSet")) return rows(procedure, String.valueOf(inputs.get(1)));
                if (name.equals("getConnection")) return connect("jdbc:bank-fixture:test", new Properties());
                if (name.equals("isClosed") || name.equals("isWrapperFor")) return false;
                if (name.equals("toString")) return "BankIntegrationFixtureStatement";
                return empty(method.getReturnType());
            });
    }

    private ResultSet rows(boolean procedure, String client) {
        int[] index = {0};
        Map<String,String> values = Map.of("LINK_ID","ACCOUNTS", "LINK_URL","/accounts/" + client,
            "IS_EXTERNAL","N", "ICON_CODE","account", "DESCRIPTION","Account overview");
        return (ResultSet) Proxy.newProxyInstance(getClass().getClassLoader(), new Class<?>[]{ResultSet.class},
            (proxy, method, args) -> switch (method.getName()) {
                case "next" -> !client.equals("MISSING") && index[0]++ == 0;
                case "getString", "getObject" -> args[0] instanceof Integer ? "Account overview" : values.get(String.valueOf(args[0]).toUpperCase(Locale.ROOT));
                case "isClosed", "wasNull", "isWrapperFor" -> false;
                case "toString" -> "BankIntegrationFixtureResultSet";
                default -> empty(method.getReturnType());
            });
    }

    private static Object empty(Class<?> type) {
        if (!type.isPrimitive() || type == void.class) return null;
        if (type == boolean.class) return false;
        if (type == long.class) return 0L;
        if (type == double.class) return 0D;
        if (type == float.class) return 0F;
        if (type == short.class) return (short) 0;
        if (type == byte.class) return (byte) 0;
        if (type == char.class) return '\0';
        return 0;
    }

    @Override public DriverPropertyInfo[] getPropertyInfo(String url, Properties properties) { return new DriverPropertyInfo[0]; }
    @Override public int getMajorVersion() { return 1; }
    @Override public int getMinorVersion() { return 0; }
    @Override public boolean jdbcCompliant() { return false; }
    @Override public Logger getParentLogger() { return Logger.getLogger("validation"); }
}
