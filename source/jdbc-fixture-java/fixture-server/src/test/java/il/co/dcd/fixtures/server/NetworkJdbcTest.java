package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.jdbc.FixtureDriver;
import il.co.dcd.fixtures.protocol.*;
import com.zaxxer.hikari.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import java.net.*;
import java.nio.file.*;
import java.sql.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

class NetworkJdbcTest {
    @TempDir Path temporary;
    private FixtureServer server;
    private String url;
    @BeforeEach void start() throws Exception {
        server=new FixtureServer(TestAssets.load(TestAssets.publish(temporary,TestAssets.queries())),new InetSocketAddress("127.0.0.1",0),"owner",false,"development");
        server.start();url="jdbc:fixtures://127.0.0.1:"+server.port()+"/success?execution=test";
        Class.forName(FixtureDriver.class.getName());
    }
    @AfterEach void stop() { if(server!=null)server.close(); }
    @Test void preparedQueryPreservesColumnsNullsAndRepeatedResults() throws Exception {
        assertNull(new FixtureDriver().connect("jdbc:postgresql://host/db",new Properties()));
        try(Connection connection=DriverManager.getConnection(url)) {
            assertTrue(connection.getMetaData().getURL().startsWith("jdbc:fixtures://"));
            assertTrue(connection.isValid(2));assertTrue(connection.getAutoCommit());connection.setReadOnly(true);assertTrue(connection.isReadOnly());
            try(PreparedStatement statement=connection.prepareStatement("SELECT Value FROM T WHERE Id = ?")) {
                statement.setLong(1,7);
                for(int i=0;i<2;i++)try(ResultSet result=statement.executeQuery()) {
                    assertTrue(result.next());assertEquals("שלום\r\n<xml>",result.getString("Value"));assertNull(result.getObject("Optional"));assertTrue(result.wasNull());assertFalse(result.next());
                }
                statement.close();assertThrows(SQLException.class,statement::executeQuery);
            }
            connection.close();assertFalse(connection.isValid(1));assertTrue(connection.isClosed());
        }
    }
    @Test void callableOutputsAndInputIndexGaps() throws Exception {
        try(Connection connection=DriverManager.getConnection(url);CallableStatement statement=connection.prepareCall("{call TEST(?,?,?)}")) {
            statement.setString(1,"C");statement.registerOutParameter(2,Types.VARCHAR);statement.registerOutParameter(3,Types.REF_CURSOR);
            assertFalse(statement.execute());assertEquals("210",statement.getString(2));
            try(ResultSet cursor=(ResultSet)statement.getObject(3)){assertTrue(cursor.next());assertEquals(7,cursor.getInt("Id"));}
        }
    }
    @Test void preparedExceptionsAndMissesRemainDistinctEvenIfCaught() throws Exception {
        try(Connection connection=DriverManager.getConnection(url)) {
            try(PreparedStatement statement=connection.prepareStatement("SELECT Failure")) {
                SQLException error=assertThrows(SQLException.class,statement::executeQuery);assertEquals("FXPRE",error.getSQLState());assertEquals("prepared failure",error.getMessage());
            }
            try(PreparedStatement statement=connection.prepareStatement("SELECT Missing")) {
                assertEquals("FXMIS",assertThrows(SQLException.class,statement::executeQuery).getSQLState());
            }
        }
        Map<String,Object> report=ServerLifecycle.request(URI.create("http://127.0.0.1:"+server.port()),"GET","/v1/reports/test",null);
        assertEquals(true,report.get("failed"));assertTrue(report.toString().contains("FIXTURE_MISS"));
    }
    @Test void realHikariResetsConnectionStateWithoutConsumingFixtures() throws Exception {
        HikariConfig config=new HikariConfig();config.setJdbcUrl(url);config.setDriverClassName(FixtureDriver.class.getName());config.setMaximumPoolSize(2);config.setMinimumIdle(0);config.setInitializationFailTimeout(-1);
        try(HikariDataSource pool=new HikariDataSource(config)) {
            try(Connection c=pool.getConnection()){c.setAutoCommit(false);c.setReadOnly(true);c.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);}
            try(Connection c=pool.getConnection()){assertTrue(c.getAutoCommit());assertFalse(c.isReadOnly());assertEquals(Connection.TRANSACTION_READ_COMMITTED,c.getTransactionIsolation());}
            ExecutorService executor=Executors.newFixedThreadPool(2);
            try {
                List<Future<String>> results=new ArrayList<>();
                for(int i=0;i<6;i++)results.add(executor.submit(()->{try(Connection c=pool.getConnection();PreparedStatement p=c.prepareStatement("SELECT Value FROM T WHERE Id = ?")){p.setInt(1,7);try(ResultSet r=p.executeQuery()){r.next();return r.getString(1);}}}));
                for(Future<String> result:results)assertEquals("שלום\r\n<xml>",result.get(20,TimeUnit.SECONDS));
            }finally{executor.shutdownNow();}
        }
    }
    @Test void explicitUnsupportedMethodsAndNetworkFailure() throws Exception {
        try(Connection connection=DriverManager.getConnection(url)) {
            assertThrows(SQLFeatureNotSupportedException.class,connection::createStatement);
            server.close();assertFalse(connection.isValid(1));assertThrows(SQLException.class,connection::getAutoCommit);
            assertThrows(SQLException.class,connection::close);assertTrue(connection.isClosed());
        }
    }
    @Test void sharedRuntimeRegistryUsesTheSameDriverWithoutApplicationChanges() throws Exception {
        Path repository=Path.of(System.getProperty("user.dir")).toAbsolutePath().getParent().getParent();
        Path source=repository.resolve("integration-runtime-java/src/main/java/il/co/dcd/integration");
        Path compiled=temporary.resolve("shared-runtime");Files.createDirectories(compiled);
        var compiler=javax.tools.ToolProvider.getSystemJavaCompiler();
        List<String> args=new ArrayList<>(List.of("-classpath",System.getProperty("java.class.path"),"-d",compiled.toString()));
        for(String file:List.of("NativeRuntimeProperties.java","DatabaseRegistry.java","PooledDatabaseRegistry.java"))args.add(source.resolve(file).toString());
        assertEquals(0,compiler.run(null,null,null,args.toArray(String[]::new)));
        try(var loader=new URLClassLoader(new URL[]{compiled.toUri().toURL()},getClass().getClassLoader())) {
            Class<?> properties=loader.loadClass("il.co.dcd.integration.NativeRuntimeProperties");Object p=properties.getConstructor().newInstance();
            Class<?> db=loader.loadClass(properties.getName()+"$Database");Object database=db.getConstructor().newInstance();
            db.getMethod("setJdbcUrl",String.class).invoke(database,url);db.getMethod("setDriverClass",String.class).invoke(database,FixtureDriver.class.getName());
            ((Map)properties.getMethod("getDatabases").invoke(p)).put("default",database);
            Class<?> registry=loader.loadClass("il.co.dcd.integration.PooledDatabaseRegistry");
            try(AutoCloseable r=(AutoCloseable)registry.getConstructor(properties).newInstance(p)) {
                javax.sql.DataSource pool=(javax.sql.DataSource)registry.getMethod("resolve",String.class).invoke(r,"default");
                try(Connection c=pool.getConnection()){assertTrue(c.isValid(1));}
            }
        }
    }
}
