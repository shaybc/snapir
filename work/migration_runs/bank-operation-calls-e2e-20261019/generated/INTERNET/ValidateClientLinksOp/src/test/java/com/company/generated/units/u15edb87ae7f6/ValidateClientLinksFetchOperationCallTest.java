package com.company.generated.units.u15edb87ae7f6;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

public class ValidateClientLinksFetchOperationCallTest {

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
        step = new ValidateClientLinksFetchStep("http://target-host:9000/", httpClient, requestMapper, successMapper, errorMapper);
    }

    @Test
    public void testNativeOperationCallContractAndEndpoint() throws Exception {
        GetClientLinksRequest req = new GetClientLinksRequest("456", "002");
        when(requestMapper.toBusinessInput(any())).thenReturn(req);

        String successXml = "<GetClientLinksResponse><ClientId>456</ClientId><Links/></GetClientLinksResponse>";
        @SuppressWarnings("unchecked")
        HttpResponse<String> resp = mock(HttpResponse.class);
        when(resp.body()).thenReturn(successXml);
        when(httpClient.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class)))
                .thenReturn(resp);

        GetClientLinksRSFmtMapper.GetClientLinksResponse parsed = new GetClientLinksRSFmtMapper.GetClientLinksResponse("456", java.util.List.of());
        when(successMapper.unformat(successXml)).thenReturn(parsed);

        int result = step.execute("456", "002");
        assertEquals(0, result);

        verify(httpClient).send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class));
    }
}