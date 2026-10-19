package com.company.generated.units.u41def216c2ea;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

public class OverviewValidateLinksStepTest {
    private HttpServer server;
    private String baseUrl;
    private OverviewValidateLinksStep step;
    private HttpClient httpClient;

    @BeforeEach
    public void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.start();
        int port = server.getAddress().getPort();
        baseUrl = "http://localhost:" + port;
        httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
        step = new OverviewValidateLinksStep(baseUrl, httpClient, new GetClientLinksRSFmtMapper(), new StandardErrorRSFmtMapper());
    }

    @AfterEach
    public void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    public void testSuccessfulValidation() throws Exception {
        server.createContext("/operations/INTERNET/ValidateClientLinksOp", new HttpHandler() {
            @Override
            public void handle(HttpExchange exchange) throws IOException {
                assertEquals("POST", exchange.getRequestMethod());
                String responseXml = "<GetClientLinksResponse><ClientId>C123</ClientId><Links><Link><LinkId>L1</LinkId><LinkUrl>http://url</LinkUrl><IsExternal>false</IsExternal></Link></Links></GetClientLinksResponse>";
                exchange.getResponseHeaders().set("Content-Type", "application/xml");
                exchange.sendResponseHeaders(200, responseXml.getBytes().length);
                OutputStream os = exchange.getResponseBody();
                os.write(responseXml.getBytes());
                os.close();
            }
        });

        GetClientLinksRequest req = new GetClientLinksRequest("C123", "0001");
        OverviewValidateLinksResult result = step.execute(req);

        assertTrue(result.isSuccess());
        assertEquals(0, result.returnCode());
        assertEquals("OverviewRefreshLinks", result.nextTransition());
        assertNotNull(result.successResponse());
        assertEquals("C123", result.successResponse().clientId());
        assertEquals(1, result.successResponse().links().size());
        assertEquals("L1", result.successResponse().links().get(0).linkId());
    }

    @Test
    public void testBusinessErrorResponse() throws Exception {
        server.createContext("/operations/INTERNET/ValidateClientLinksOp", new HttpHandler() {
            @Override
            public void handle(HttpExchange exchange) throws IOException {
                String errorXml = "<ErrorReply><ErrorCategory>VALIDATION</ErrorCategory><ErrorNumber>E001</ErrorNumber><ErrorDescription>Invalid Link</ErrorDescription><RequestId>R1</RequestId></ErrorReply>";
                exchange.getResponseHeaders().set("Content-Type", "application/xml");
                exchange.sendResponseHeaders(400, errorXml.getBytes().length);
                OutputStream os = exchange.getResponseBody();
                os.write(errorXml.getBytes());
                os.close();
            }
        });

        GetClientLinksRequest req = new GetClientLinksRequest("C123", "0001");
        OverviewValidateLinksResult result = step.execute(req);

        assertFalse(result.isSuccess());
        assertEquals(400, result.returnCode());
        assertEquals("end", result.nextTransition());
        assertNotNull(result.errorReply());
        assertEquals("VALIDATION", result.errorReply().errorCategory());
        assertEquals("E001", result.errorReply().errorNumber());
        assertEquals("Invalid Link", result.errorReply().errorDescription());
    }

    @Test
    public void testTransportFailureOrTimeout() {
        OverviewValidateLinksStep badStep = new OverviewValidateLinksStep("http://localhost:1", httpClient, new GetClientLinksRSFmtMapper(), new StandardErrorRSFmtMapper());
        GetClientLinksRequest req = new GetClientLinksRequest("C123", "0001");
        Exception ex = assertThrows(Exception.class, () -> {
            badStep.execute(req);
        });
        assertNotNull(ex);
    }
}