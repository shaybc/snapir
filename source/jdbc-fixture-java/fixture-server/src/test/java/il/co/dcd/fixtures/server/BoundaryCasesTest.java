package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.jdbc.FixtureDriver;
import il.co.dcd.fixtures.protocol.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.sql.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class BoundaryCasesTest {
    @TempDir Path temporary;
    private FixtureServer server;
    private String url;
    @BeforeEach void start() throws Exception {
        var queries=new ArrayList<>(TestAssets.queries());
        queries.add(Map.of("sql","SELECT Typed","parameters",List.of(),"columns",List.of("Amount","Date"),
            "rows",List.of(List.of(Map.of("$decimal","1234567890.0100"),Map.of("$date_millis",1704153600000L)))));
        server=new FixtureServer(TestAssets.load(TestAssets.publish(temporary,queries)),new InetSocketAddress("127.0.0.1",0),"owner",false,"development");
        server.start();url="jdbc:fixtures://127.0.0.1:"+server.port()+"/success?execution=boundary";
        Class.forName(FixtureDriver.class.getName());
    }
    @AfterEach void stop(){server.close();}
    @Test void mismatchedSqlAndOutputRegistrationsAreExplicitMisses() throws Exception {
        try(Connection c=DriverManager.getConnection(url)) {
            try(PreparedStatement p=c.prepareStatement("select Value FROM T WHERE Id = ?")) {
                p.setInt(1,7);assertEquals("FXMIS",assertThrows(SQLException.class,p::executeQuery).getSQLState());
            }
            try(CallableStatement p=c.prepareCall("{call TEST(?,?,?)}")) {
                p.setString(1,"C");p.registerOutParameter(2,Types.INTEGER);p.registerOutParameter(3,Types.REF_CURSOR);
                assertEquals("FXMIS",assertThrows(SQLException.class,p::execute).getSQLState());
            }
        }
    }
    @Test void decimalPrecisionDatesAndClosedOwnerArePreserved() throws Exception {
        try(Connection c=DriverManager.getConnection(url);PreparedStatement p=c.prepareStatement("SELECT Typed")) {
            ResultSet result=p.executeQuery();assertTrue(result.next());
            assertEquals("1234567890.0100",result.getBigDecimal("Amount").toPlainString());
            assertEquals(1704153600000L,result.getDate("Date").getTime());
            p.close();assertTrue(result.isClosed());assertThrows(SQLException.class,result::next);
        }
    }
    @Test void unsupportedGetterRemainsStickyOutsideApplication() throws Exception {
        try(Connection c=DriverManager.getConnection(url);PreparedStatement p=c.prepareStatement("SELECT Typed");ResultSet r=p.executeQuery()) {
            r.next();assertThrows(SQLFeatureNotSupportedException.class,()->r.getShort("Amount"));
        }
        assertEquals(true,ServerLifecycle.request(URI.create("http://127.0.0.1:"+server.port()),"GET","/v1/reports/boundary",null).get("failed"));
    }
    @Test void expectedSqlExceptionAloneDoesNotMarkInfrastructureFailure() throws Exception {
        try(Connection c=DriverManager.getConnection(url);PreparedStatement p=c.prepareStatement("SELECT Failure")) {
            assertEquals("FXPRE",assertThrows(SQLException.class,p::executeQuery).getSQLState());
        }
        assertEquals(false,ServerLifecycle.request(URI.create("http://127.0.0.1:"+server.port()),"GET","/v1/reports/boundary",null).get("failed"));
    }
    @Test void independentConnectionsDoNotShareMutableState() throws Exception {
        try(Connection a=DriverManager.getConnection(url);Connection b=DriverManager.getConnection(url)) {
            a.setReadOnly(true);a.setAutoCommit(false);assertFalse(b.isReadOnly());assertTrue(b.getAutoCommit());
            a.close();assertTrue(b.isValid(1));
        }
    }
    @Test void protocolMismatchCannotOpenConnection() throws Exception {
        HttpRequest request=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+server.port()+"/v1/connections"))
            .POST(HttpRequest.BodyPublishers.ofByteArray(Json.bytes(Map.of("protocol",2,"scenario","success","execution","bad")))).build();
        try(HttpClient client=HttpClient.newHttpClient()) {
            var response=client.send(request,HttpResponse.BodyHandlers.ofByteArray());
            assertEquals("PROTOCOL_MISMATCH",Json.object(Json.read(response.body())).get("code"));
        }
    }
    @Test void unavailableMetadataAndVendorWrappersRemainSticky() throws Exception {
        try(Connection c=DriverManager.getConnection(url)) {
            assertThrows(SQLException.class,()->c.unwrap(Runnable.class));
            assertThrows(SQLFeatureNotSupportedException.class,()->c.getMetaData().getTables(null,null,null,null));
        }
        assertEquals(true,ServerLifecycle.request(URI.create("http://127.0.0.1:"+server.port()),"GET","/v1/reports/boundary",null).get("failed"));
    }
    @Test void invalidOutputOrInputIndexGapDoesNotUseAnotherFixture() throws Exception {
        try(Connection c=DriverManager.getConnection(url);CallableStatement p=c.prepareCall("{call TEST(?,?,?)}")) {
            p.setString(2,"C");p.registerOutParameter(3,Types.VARCHAR);p.registerOutParameter(4,Types.REF_CURSOR);
            assertEquals("FXMIS",assertThrows(SQLException.class,p::execute).getSQLState());
        }
    }
}
