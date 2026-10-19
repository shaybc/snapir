package com.company.generated.units.u15edb87ae7f6;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;

public class ValidateClientLinksFetchStep {

    private final String baseUrl;
    private final HttpClient httpClient;
    private final GetClientLinksRequestUnformatMapper requestMapper;
    private final GetClientLinksRSFmtMapper successMapper;
    private final StandardErrorRSFmtMapper errorMapper;

    public ValidateClientLinksFetchStep(String baseUrl,
                                         HttpClient httpClient,
                                         GetClientLinksRequestUnformatMapper requestMapper,
                                         GetClientLinksRSFmtMapper successMapper,
                                         StandardErrorRSFmtMapper errorMapper) {
        this.baseUrl = Objects.requireNonNull(baseUrl, "baseUrl");
        this.httpClient = Objects.requireNonNull(httpClient, "httpClient");
        this.requestMapper = Objects.requireNonNull(requestMapper, "requestMapper");
        this.successMapper = Objects.requireNonNull(successMapper, "successMapper");
        this.errorMapper = Objects.requireNonNull(errorMapper, "errorMapper");
    }

    public int execute(String clientId, String bankId) throws Exception {
        GetClientLinksRequestXml xmlReq = new GetClientLinksRequestXml();
        xmlReq.clientId = clientId;
        xmlReq.bankId = bankId;
        GetClientLinksRequest request = requestMapper.toBusinessInput(xmlReq);

        StringBuilder sb = new StringBuilder();
        sb.append("<GetClientLinks>");
        sb.append("<ClientId>").append(escapeXml(request.getClientId())).append("</ClientId>");
        sb.append("<BankId>").append(escapeXml(request.getBankId())).append("</BankId>");
        sb.append("</GetClientLinks>");

        String base = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        String urlStr = base + "/operations/INTERNET/GetClientLinksOp";

        HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(urlStr))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/xml")
                .POST(HttpRequest.BodyPublishers.ofString(sb.toString()))
                .build();

        HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
        String body = response.body();

        if (body != null && body.contains("ErrorReply")) {
            errorMapper.unformat(body);
            return 1;
        } else if (body != null && body.contains("GetClientLinksResponse")) {
            successMapper.unformat(body);
            return 0;
        }
        return 0;
    }

    private String escapeXml(String val) {
        if (val == null) return "";
        return val.replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace("\"", "&quot;")
                  .replace("'", "&apos;");
    }
}