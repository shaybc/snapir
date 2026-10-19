package com.company.generated.units.u15edb87ae7f6;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

public class ValidateClientLinksFetchStepAdapterTest {

    private HttpClient httpClient;
    private GetClientLinksRequestUnformatMapper requestMapper;
    private GetClientLinksRSFmtMapper successMapper;
    private StandardErrorRSFmtMapper errorMapper;
    private ValidateClientLinksFetchStep step;

    @BeforeEach
    public void setUp() {
        httpClient = mock(HttpClient.class);
        requestMapper = mock(GetClientLinksRequestUnformatMapper.class);
        successMapper = mock(GetClientLinksRSFmtMapper.class);
        errorMapper = mock(StandardErrorRSFmtMapper.class);
        step = new ValidateClientLinksFetchStep("http://localhost:8080", httpClient, requestMapper, successMapper, errorMapper);
    }

    @Test
    public void testTransportFailureThrowsException() throws Exception {
        GetClientLinksRequest req = new GetClientLinksRequest("123", "001");
        when(requestMapper.toBusinessInput(any())).thenReturn(req);

        when(httpClient.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class)))
                .thenThrow(new IOException("Connection timeout"));

        assertThrows(Exception.class, () -> step.execute("123", "001"));
    }
}