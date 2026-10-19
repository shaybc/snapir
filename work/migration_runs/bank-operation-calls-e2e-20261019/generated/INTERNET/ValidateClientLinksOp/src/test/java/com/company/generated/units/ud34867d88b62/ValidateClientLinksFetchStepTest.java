package com.company.generated.units.ud34867d88b62;

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

import static org.junit.jupiter.api.Assertions.*;

public class ValidateClientLinksFetchStepTest {
    private HttpServer server;
    private String baseUrl;

    @BeforeEach
    public void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        int port = server.getAddress().getPort();
        baseUrl = "http://localhost:" + port;
    }

    @AfterEach
    public void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    public void testSuccessfulFetchAndOperationCall() throws Exception {
        server.createContext("/operations/INTERNET/GetClientLinksOp", new HttpHandler() {
            @Override
            public void handle(HttpExchange exchange) throws IOException {
                assertEquals("POST", exchange.getRequestMethod());
                assertEquals("application/xml", exchange.getRequestHeaders().getFirst("Content-Type"));
                String responseXml = "<GetClientLinksResponse><ClientId>12345</ClientId><Links><Link><LinkId>L1</LinkId><LinkUrl>http://example.com</LinkUrl><IsExternal>true</IsExternal></Link></Links></GetClientLinksResponse>";
                exchange.sendResponseHeaders(200, responseXml.getBytes().length);
                OutputStream os = exchange.getResponseBody();
                os.write(responseXml.getBytes());
                os.close();
            }
        });
        server.start();

        OperationContextBridge context = new OperationContextBridge();
        context.setValueAt("ClientId", "12345");
        context.setValueAt("BankId", "0123");

        ValidateClientLinksFetchStep step = new ValidateClientLinksFetchStep(
                baseUrl,
                HttpClient.newHttpClient(),
                null,
                new GetClientLinksRSFmtMapper(),
                new StandardErrorRSFmtMapper()
        );
        step.setContext(context);

        int rc = step.execute();
        assertEquals(0, rc);
        assertEquals("0", context.getValueAt("ERROR_CODE"));
        assertNotNull(context.getValueAt("GetClientLinksResponse"));
    }

    @Test
    public void testErrorReplyFetch() throws Exception {
        server.createContext("/operations/INTERNET/GetClientLinksOp", new HttpHandler() {
            @Override
            public void handle(HttpExchange exchange) throws IOException {
                String errorXml = "<ErrorReply><ErrorCategory>CAT</ErrorCategory><ErrorNumber>99</ErrorNumber><ErrorDescription>Not Found</ErrorDescription><RequestId>REQ1</RequestId></ErrorReply>";
                exchange.sendResponseHeaders(400, errorXml.getBytes().length);
                OutputStream os = exchange.getResponseBody();
                os.write(errorXml.getBytes());
                os.close();
            }
        });
        server.start();

        OperationContextBridge context = new OperationContextBridge();
        context.setValueAt("ClientId", "12345");
        context.setValueAt("BankId", "0123");

        ValidateClientLinksFetchStep step = new ValidateClientLinksFetchStep(
                baseUrl,
                HttpClient.newHttpClient(),
                null,
                new GetClientLinksRSFmtMapper(),
                new StandardErrorRSFmtMapper()
        );
        step.setContext(context);

        int rc = step.execute();
        assertEquals(-1, rc);
        assertEquals("99", context.getValueAt("ERROR_CODE"));
        assertNotNull(context.getValueAt("ErrorReply"));
    }

    @Test
    public void testTransportFailure() {
        OperationContextBridge context = new OperationContextBridge();
        context.setValueAt("ClientId", "12345");
        context.setValueAt("BankId", "0123");

        ValidateClientLinksFetchStep step = new ValidateClientLinksFetchStep(
                "http://localhost:1",
                HttpClient.newBuilder().connectTimeout(java.time.Duration.ofMillis(100)).build(),
                null,
                new GetClientLinksRSFmtMapper(),
                new StandardErrorRSFmtMapper()
        );
        step.setContext(context);

        assertThrows(Exception.class, () -> step.execute());
    }
}