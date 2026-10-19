package com.company.generated.units.u823fe183c8e4;

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

public class OverviewRefreshLinksStep {
    private final String baseUrl;
    private final HttpClient httpClient;
    private final GetClientLinksRequestUnformatMapper requestMapper;
    private final GetClientLinksRSFmtMapper responseMapper;
    private final StandardErrorRSFmtMapper errorMapper;

    public OverviewRefreshLinksStep(String baseUrl, HttpClient httpClient,
                                     GetClientLinksRequestUnformatMapper requestMapper,
                                     GetClientLinksRSFmtMapper responseMapper,
                                     StandardErrorRSFmtMapper errorMapper) {
        this.baseUrl = Objects.requireNonNull(baseUrl, "Base URL");
        this.httpClient = httpClient != null ? httpClient : HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        this.requestMapper = requestMapper != null ? requestMapper : new GetClientLinksRequestUnformatMapper();
        this.responseMapper = responseMapper != null ? responseMapper : new GetClientLinksRSFmtMapper();
        this.errorMapper = errorMapper != null ? errorMapper : new StandardErrorRSFmtMapper();
    }

    public int execute(String clientId, String bankId) throws Exception {
        GetClientLinksRequest requestDto = new GetClientLinksRequest(clientId, bankId);
        GetClientLinksRequestXml requestXmlObj = new GetClientLinksRequestXml();
        requestXmlObj.clientId = clientId;
        requestXmlObj.bankId = bankId;
        
        XmlMapper xmlMapper = new XmlMapper();
        String requestBody = xmlMapper.writeValueAsString(requestXmlObj);

        String targetUrl = baseUrl.replaceAll("/$", "") + "/operations/INTERNET/GetClientLinksOp";
        HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(targetUrl))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/xml")
                .header("Accept", "application/xml")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() == 200) {
            String respXml = response.body();
            GetClientLinksRSFmtMapper.GetClientLinksResponse parsedResponse = responseMapper.unformat(respXml);
            if (parsedResponse != null) {
                return 0;
            }
            return 1;
        } else if (response.statusCode() >= 400 && response.statusCode() < 600) {
            String errXml = response.body();
            StandardErrorRSFmtMapper.ErrorReply errorReply = errorMapper.unformat(errXml);
            if (errorReply != null) {
                return 99;
            }
            return 1;
        } else {
            return 1;
        }
    }
}