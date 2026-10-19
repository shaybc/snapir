package com.company.generated.units.u41def216c2ea;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;

public class OverviewValidateLinksStep {
    private final String baseUrl;
    private final HttpClient httpClient;
    private final GetClientLinksRSFmtMapper successMapper;
    private final StandardErrorRSFmtMapper errorMapper;

    public OverviewValidateLinksStep(String baseUrl, HttpClient httpClient, GetClientLinksRSFmtMapper successMapper, StandardErrorRSFmtMapper errorMapper) {
        this.baseUrl = Objects.requireNonNull(baseUrl, "baseUrl");
        this.httpClient = Objects.requireNonNull(httpClient, "httpClient");
        this.successMapper = Objects.requireNonNull(successMapper, "successMapper");
        this.errorMapper = Objects.requireNonNull(errorMapper, "errorMapper");
    }

    public OverviewValidateLinksResult execute(GetClientLinksRequest request) throws Exception {
        String requestXml = "<GetClientLinks><ClientId>" + escapeXml(request.getClientId()) + "</ClientId><BankId>" + escapeXml(request.getBankId()) + "</BankId></GetClientLinks>";
        HttpRequest httpRequest = HttpRequest.newBuilder()
            .uri(URI.create(baseUrl + "/operations/INTERNET/ValidateClientLinksOp"))
            .header("Content-Type", "application/xml")
            .header("Accept", "application/xml")
            .timeout(Duration.ofSeconds(30))
            .POST(HttpRequest.BodyPublishers.ofString(requestXml))
            .build();

        HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
        int statusCode = response.statusCode();
        String responseBody = response.body();

        if (statusCode >= 200 && statusCode < 300) {
            GetClientLinksRSFmtMapper.GetClientLinksResponse successResponse = successMapper.unformat(responseBody);
            return new OverviewValidateLinksResult(0, successResponse, null);
        } else {
            try {
                StandardErrorRSFmtMapper.ErrorReply errorReply = errorMapper.unformat(responseBody);
                return new OverviewValidateLinksResult(statusCode, null, errorReply);
            } catch (Exception e) {
                return new OverviewValidateLinksResult(statusCode, null, new StandardErrorRSFmtMapper.ErrorReply("TRANSPORT", String.valueOf(statusCode), responseBody, null));
            }
        }
    }

    private String escapeXml(String value) {
        if (value == null) return "";
        return value.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\"", "&quot;")
                    .replace("'", "&apos;");
    }
}