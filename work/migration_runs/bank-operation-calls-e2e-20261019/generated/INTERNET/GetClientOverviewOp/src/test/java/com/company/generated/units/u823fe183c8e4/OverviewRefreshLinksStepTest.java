package com.company.generated.units.u823fe183c8e4;

import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import org.junit.jupiter.api.Test;
import java.net.http.HttpClient;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class OverviewRefreshLinksStepTest {

    @Test
    public void testSuccessfulExecution() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        @SuppressWarnings("unchecked")
        HttpResponse<String> httpResponse = (HttpResponse<String>) mock(HttpResponse.class);

        when(httpResponse.statusCode()).thenReturn(200);
        when(httpResponse.body()).thenReturn("<GetClientLinksResponse><ClientId>12345</ClientId><Links/></GetClientLinksResponse>");
        doReturn(httpResponse).when(httpClient).send(any(), any());

        OverviewRefreshLinksStep step = new OverviewRefreshLinksStep(
                "http://localhost:8080", httpClient, null, null, null);

        int rc = step.execute("12345", "0123");
        assertEquals(0, rc);
        verify(httpClient).send(any(), any());
    }

    @Test
    public void testBusinessErrorExecution() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        @SuppressWarnings("unchecked")
        HttpResponse<String> httpResponse = (HttpResponse<String>) mock(HttpResponse.class);

        when(httpResponse.statusCode()).thenReturn(500);
        when(httpResponse.body()).thenReturn("<ErrorReply><ErrorCategory>ERR</ErrorCategory><ErrorNumber>001</ErrorNumber><ErrorDescription>Failed</ErrorDescription><RequestId>REQ1</RequestId></ErrorReply>");
        doReturn(httpResponse).when(httpClient).send(any(), any());

        OverviewRefreshLinksStep step = new OverviewRefreshLinksStep(
                "http://localhost:8080", httpClient, null, null, null);

        int rc = step.execute("12345", "0123");
        assertEquals(99, rc);
        verify(httpClient).send(any(), any());
    }

    @Test
    public void testTransportFailure() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        when(httpClient.send(any(), any())).thenThrow(new java.net.http.HttpConnectTimeoutException("Connection timed out"));

        OverviewRefreshLinksStep step = new OverviewRefreshLinksStep(
                "http://localhost:8080", httpClient, null, null, null);

        assertThrows(java.net.http.HttpConnectTimeoutException.class, () -> {
            step.execute("12345", "0123");
        });
    }

    @Test
    public void testTimeoutHandling() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        when(httpClient.send(any(), any())).thenThrow(new java.net.http.HttpTimeoutException("Request timed out"));

        OverviewRefreshLinksStep step = new OverviewRefreshLinksStep(
                "http://localhost:8080", httpClient, null, null, null);

        assertThrows(java.net.http.HttpTimeoutException.class, () -> {
            step.execute("12345", "0123");
        });
    }
}