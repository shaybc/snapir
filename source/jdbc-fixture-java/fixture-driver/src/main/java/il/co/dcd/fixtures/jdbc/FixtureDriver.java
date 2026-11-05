package il.co.dcd.fixtures.jdbc;

import il.co.dcd.fixtures.protocol.FixtureUrl;
import java.sql.*;
import java.util.Properties;
import java.util.logging.Logger;

/** Standard JDBC entry point for the network fixture service, never real database URLs. */
public final class FixtureDriver implements Driver {
    static { try { DriverManager.registerDriver(new FixtureDriver()); } catch (SQLException e) { throw new ExceptionInInitializerError(e); } }
    @Override public boolean acceptsURL(String url) { return url!=null && url.startsWith(FixtureUrl.PREFIX); }
    @Override public Connection connect(String url,Properties properties) throws SQLException {
        if (!acceptsURL(url)) return null;
        try { return ConnectionHandler.open(FixtureUrl.parse(url), properties==null ? new Properties() : properties); }
        catch (IllegalArgumentException e) { throw new SQLException("Invalid fixture JDBC configuration","08001",e); }
    }
    @Override public DriverPropertyInfo[] getPropertyInfo(String url,Properties properties) {
        return new DriverPropertyInfo[]{new DriverPropertyInfo("connectTimeoutMs","5000"),new DriverPropertyInfo("readTimeoutMs","10000")};
    }
    @Override public int getMajorVersion() { return 1; }
    @Override public int getMinorVersion() { return 0; }
    @Override public boolean jdbcCompliant() { return false; }
    @Override public Logger getParentLogger() { return Logger.getLogger("il.co.dcd.fixtures.jdbc"); }
}
