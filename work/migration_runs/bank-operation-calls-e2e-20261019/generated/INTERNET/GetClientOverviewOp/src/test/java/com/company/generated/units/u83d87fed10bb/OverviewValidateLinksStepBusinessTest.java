package com.company.generated.units.u83d87fed10bb;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import java.net.http.HttpClient;
import java.net.http.HttpResponse;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class OverviewValidateLinksStepBusinessTest {

    @Test
    public void testValidClientLinksReturnsSuccessCodeZero() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        HttpResponse<String> httpResponse = mock(HttpResponse.class);
        GetClientLinksRequestUnformatMapper requestMapper = mock(GetClientLinksRequestUnformatMapper.class);
        GetClientLinksRSFmtMapper responseMapper = mock(GetClientLinksRSFmtMapper.class);
        StandardErrorRSFmtMapper errorMapper = mock(StandardErrorRSFmtMapper.class);

        GetClientLinksRequest businessReq = new GetClientLinksRequest("123456", "0012");
        when(requestMapper.toBusinessInput(any(GetClientLinksRequestXml.class))).thenReturn(businessReq);

        GetClientLinksRSFmtMapper.GetClientLinksResponse successResp =
                new GetClientLinksRSFmtMapper.GetClientLinksResponse("123456", List.of());
        when(responseMapper.unformat(any(String.class))).thenReturn(successResp);

        when(httpClient.<String>send(any(), any())).thenReturn(httpResponse);
        when(httpResponse.statusCode()).thenReturn(200);
        when(httpResponse.body()).thenReturn("<GetClientLinksResponse><ClientId>123456</ClientId></GetClientLinksResponse>");

        OverviewValidateLinksStep step = new OverviewValidateLinksStep(
                "http://localhost:8080", httpClient, requestMapper, responseMapper, errorMapper);

        int rc = step.execute("123456", "0012");
        assertEquals(0, rc);
        verify(httpClient).send(any(), any());
    }

    @Test
    public void testBlankClientIdReturnsOtherCodeOne() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        GetClientLinksRequestUnformatMapper requestMapper = mock(GetClientLinksRequestUnformatMapper.class);
        GetClientLinksRSFmtMapper responseMapper = mock(GetClientLinksRSFmtMapper.class);
        StandardErrorRSFmtMapper errorMapper = mock(StandardErrorRSFmtMapper.class);

        GetClientLinksRequest businessReq = new GetClientLinksRequest("", "0012");
        when(requestMapper.toBusinessInput(any(GetClientLinksRequestXml.class))).thenReturn(businessReq);

        OverviewValidateLinksStep step = new OverviewValidateLinksStep(
                "http://localhost:8080", httpClient, requestMapper, responseMapper, errorMapper);

        int rc = step.execute("", "0012");
        assertEquals(1, rc);
        verifyNoInteractions(httpClient);
    }
}