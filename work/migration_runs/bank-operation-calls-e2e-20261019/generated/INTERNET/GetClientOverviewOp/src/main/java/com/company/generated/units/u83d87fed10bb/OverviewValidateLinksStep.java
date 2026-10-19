package com.company.generated.units.u83d87fed10bb;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;

public class OverviewValidateLinksStep {
    private final String baseUrl;
    private final HttpClient httpClient;
    private final GetClientLinksRequestUnformatMapper requestMapper;
    private final GetClientLinksRSFmtMapper responseMapper;
    private final StandardErrorRSFmtMapper errorMapper;
    private final XmlMapper xmlMapper;

    public OverviewValidateLinksStep(String baseUrl,
                                     HttpClient httpClient,
                                     GetClientLinksRequestUnformatMapper requestMapper,
                                     GetClientLinksRSFmtMapper responseMapper,
                                     StandardErrorRSFmtMapper errorMapper) {
        this.baseUrl = Objects.requireNonNull(baseUrl, "baseUrl");
        this.httpClient = Objects.requireNonNull(httpClient, "httpClient");
        this.requestMapper = Objects.requireNonNull(requestMapper, "requestMapper");
        this.responseMapper = Objects.requireNonNull(responseMapper, "responseMapper");
        this.errorMapper = Objects.requireNonNull(errorMapper, "errorMapper");
        this.xmlMapper = new XmlMapper();
    }

    public int execute(String clientId, String bankId) throws Exception {
        GetClientLinksRequestXml requestXml = new GetClientLinksRequestXml();
        requestXml.clientId = clientId;
        requestXml.bankId = bankId;

        GetClientLinksRequest businessInput = requestMapper.toBusinessInput(requestXml);
        if (businessInput.getClientId() == null || businessInput.getClientId().isBlank()) {
            return 1; // non-zero indicates other / error routing per onOtherDo=end or route
        }

        String requestPayload = xmlMapper.writeValueAsString(requestXml);

        String targetUrl = baseUrl.replaceAll("/$", "") + "/operations/INTERNET/ValidateClientLinksOp";
        HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(targetUrl))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/xml")
                .header("Accept", "application/xml")
                .POST(HttpRequest.BodyPublishers.ofString(requestPayload))
                .build();

        HttpResponse<String> response;
        try {
            response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
        } catch (Exception e) {
            return 1; // timeout or transport failure routes to onOtherDo (end)
        }

        int statusCode = response.statusCode();
        String responseBody = response.body();

        if (statusCode >= 200 && statusCode < 300) {
            try {
                GetClientLinksRSFmtMapper.GetClientLinksResponse parsedResponse = responseMapper.unformat(responseBody);
                if (parsedResponse != null && parsedResponse.clientId() != null) {
                    return 0; // on0Do = OverviewRefreshLinks (represented by 0)
                }
            } catch (Exception e) {
                return 1;
            }
            return 1;
        } else {
            try {
                StandardErrorRSFmtMapper.ErrorReply errorReply = errorMapper.unformat(responseBody);
                if (errorReply != null) {
                    return 1;
                }
            } catch (Exception e) {
                return 1;
            }
            return 1;
        }
    }
}