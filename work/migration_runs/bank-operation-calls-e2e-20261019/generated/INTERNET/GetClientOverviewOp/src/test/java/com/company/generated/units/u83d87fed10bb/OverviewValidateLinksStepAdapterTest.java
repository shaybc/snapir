package com.company.generated.units.u83d87fed10bb;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpResponse;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class OverviewValidateLinksStepAdapterTest {

    @Test
    public void testHttpTimeoutOrTransportFailureReturnsOtherCode() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        GetClientLinksRequestUnformatMapper requestMapper = mock(GetClientLinksRequestUnformatMapper.class);
        GetClientLinksRSFmtMapper responseMapper = mock(GetClientLinksRSFmtMapper.class);
        StandardErrorRSFmtMapper errorMapper = mock(StandardErrorRSFmtMapper.class);

        GetClientLinksRequest businessReq = new GetClientLinksRequest("123456", "0012");
        when(requestMapper.toBusinessInput(any(GetClientLinksRequestXml.class))).thenReturn(businessReq);

        when(httpClient.<String>send(any(), any())).thenThrow(new IOException("Timeout or transport failure"));

        OverviewValidateLinksStep step = new OverviewValidateLinksStep(
                "http://localhost:8080", httpClient, requestMapper, responseMapper, errorMapper);

        int rc = step.execute("123456", "0012");
        assertEquals(1, rc);
    }

    @Test
    public void testTargetBusinessErrorReplyReturnsOtherCode() throws Exception {
        HttpClient httpClient = mock(HttpClient.class);
        HttpResponse<String> httpResponse = mock(HttpResponse.class);
        GetClientLinksRequestUnformatMapper requestMapper = mock(GetClientLinksRequestUnformatMapper.class);
        GetClientLinksRSFmtMapper responseMapper = mock(GetClientLinksRSFmtMapper.class);
        StandardErrorRSFmtMapper errorMapper = mock(StandardErrorRSFmtMapper.class);

        GetClientLinksRequest businessReq = new GetClientLinksRequest("123456", "0012");
        when(requestMapper.toBusinessInput(any(GetClientLinksRequestXml.class))).thenReturn(businessReq);

        StandardErrorRSFmtMapper.ErrorReply errorReply =
                new StandardErrorRSFmtMapper.ErrorReply("SYSTEM", "E001", "Invalid Client Links", "req-123");
        when(errorMapper.unformat(any(String.class))).thenReturn(errorReply);

        when(httpClient.<String>send(any(), any())).thenReturn(httpResponse);
        when(httpResponse.statusCode()).thenReturn(500);
        when(httpResponse.body()).thenReturn("<ErrorReply><ErrorCategory>SYSTEM</ErrorCategory><ErrorNumber>E001</ErrorNumber><ErrorDescription>Invalid Client Links</ErrorDescription><RequestId>req-123</RequestId></ErrorReply>");

        OverviewValidateLinksStep step = new OverviewValidateLinksStep(
                "http://localhost:8080", httpClient, requestMapper, responseMapper, errorMapper);

        int rc = step.execute("123456", "0012");
        assertEquals(1, rc);
        verify(errorMapper).unformat(any(String.class));
    }
}