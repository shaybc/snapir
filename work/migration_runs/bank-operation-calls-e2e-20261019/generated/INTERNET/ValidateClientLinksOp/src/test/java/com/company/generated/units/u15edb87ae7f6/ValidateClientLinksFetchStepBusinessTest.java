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
import static org.mockito.Mockito.when;

public class ValidateClientLinksFetchStepBusinessTest {

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
    public void testSuccessfulFetchReturnsZero() throws Exception {
        GetClientLinksRequest req = new GetClientLinksRequest("123", "001");
        when(requestMapper.toBusinessInput(any())).thenReturn(req);

        String successXml = "<GetClientLinksResponse><ClientId>123</ClientId><Links/></GetClientLinksResponse>";
        @SuppressWarnings("unchecked")
        HttpResponse<String> resp = mock(HttpResponse.class);
        when(resp.body()).thenReturn(successXml);
        when(httpClient.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class))).thenReturn(resp);

        GetClientLinksRSFmtMapper.GetClientLinksResponse parsed = new GetClientLinksRSFmtMapper.GetClientLinksResponse("123", java.util.List.of());
        when(successMapper.unformat(successXml)).thenReturn(parsed);

        int result = step.execute("123", "001");
        assertEquals(0, result);
    }

    @Test
    public void testBusinessErrorReturnsNonZero() throws Exception {
        GetClientLinksRequest req = new GetClientLinksRequest("123", "001");
        when(requestMapper.toBusinessInput(any())).thenReturn(req);

        String errorXml = "<ErrorReply><ErrorCategory>CAT</ErrorCategory><ErrorNumber>001</ErrorNumber><ErrorDescription>ERR</ErrorDescription><RequestId>1</RequestId></ErrorReply>";
        @SuppressWarnings("unchecked")
        HttpResponse<String> resp = mock(HttpResponse.class);
        when(resp.body()).thenReturn(errorXml);
        when(httpClient.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class))).thenReturn(resp);

        StandardErrorRSFmtMapper.ErrorReply errReply = new StandardErrorRSFmtMapper.ErrorReply("CAT", "001", "ERR", "1");
        when(errorMapper.unformat(errorXml)).thenReturn(errReply);

        int result = step.execute("123", "001");
        assertEquals(1, result);
    }
}