package il.co.dcd.fixtures.jdbc;

import java.sql.*;
import java.util.function.Consumer;

/** Small truthful database/driver identity, without inventing unsupported metadata. */
final class DriverMetadata {
    private DriverMetadata() { }
    static DatabaseMetaData create(Connection connection,String url,Consumer<String> diagnostic) {
        return JdbcProxy.create(DatabaseMetaData.class,(proxy,method,args)-> {
            if (JdbcProxy.common(method)) {
                try{return JdbcProxy.common(proxy,method,args);}
                catch(SQLException e){diagnostic.accept(method.getName());throw e;}
            }
            return switch (method.getName()) {
                case "getConnection" -> connection;
                case "getURL" -> url;
                case "getDriverName", "getDatabaseProductName" -> "Fixture JDBC";
                case "getDriverVersion", "getDatabaseProductVersion" -> "1.0.0";
                case "getDriverMajorVersion", "getDatabaseMajorVersion" -> 1;
                case "getDriverMinorVersion", "getDatabaseMinorVersion" -> 0;
                case "getJDBCMajorVersion" -> 4;
                case "getJDBCMinorVersion" -> 3;
                case "supportsTransactions" -> false;
                default -> {diagnostic.accept(method.getName());throw JdbcProxy.unsupported(method);}
            };
        });
    }
}
