package il.co.dcd.fixtures.jdbc;

import java.lang.reflect.*;
import java.sql.*;

/** Shared object identity and JDBC wrapper handling; no generic success defaults. */
final class JdbcProxy {
    private JdbcProxy() { }
    static <T> T create(Class<T> type,InvocationHandler handler) {
        return type.cast(Proxy.newProxyInstance(FixtureDriver.class.getClassLoader(),new Class<?>[]{type},handler));
    }
    static boolean common(Method method) { return method.getDeclaringClass()==Object.class || method.getName().equals("unwrap") || method.getName().equals("isWrapperFor"); }
    static Object common(Object proxy,Method method,Object[] args) throws SQLException {
        return switch (method.getName()) {
            case "toString" -> "FixtureJDBC:"+proxy.getClass().getInterfaces()[0].getSimpleName();
            case "hashCode" -> System.identityHashCode(proxy);
            case "equals" -> proxy==args[0];
            case "isWrapperFor" -> ((Class<?>)args[0]).isInstance(proxy);
            case "unwrap" -> { if (!((Class<?>)args[0]).isInstance(proxy)) throw new SQLException("Unsupported JDBC wrapper"); yield proxy; }
            default -> throw unsupported(method);
        };
    }
    static SQLFeatureNotSupportedException unsupported(Method method) {
        return new SQLFeatureNotSupportedException("Unsupported fixture JDBC method: "+method.getDeclaringClass().getSimpleName()+"."+method.getName(),"FXCAP");
    }
}
