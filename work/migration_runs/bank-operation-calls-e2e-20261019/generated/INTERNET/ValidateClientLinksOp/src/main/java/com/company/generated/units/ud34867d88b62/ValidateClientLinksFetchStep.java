package com.company.generated.units.ud34867d88b62;

import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;

public class ValidateClientLinksFetchStep {
    private final String baseUrl;
    private final HttpClient httpClient;
    private final GetClientLinksRequestUnformatMapper requestUnformatMapper;
    private final GetClientLinksRSFmtMapper successMapper;
    private final StandardErrorRSFmtMapper errorMapper;
    private OperationContextBridge context;

    public ValidateClientLinksFetchStep(String baseUrl, HttpClient httpClient,
                                        GetClientLinksRequestUnformatMapper requestUnformatMapper,
                                        GetClientLinksRSFmtMapper successMapper,
                                        StandardErrorRSFmtMapper errorMapper) {
        this.baseUrl = Objects.requireNonNull(baseUrl, "Base URL");
        this.httpClient = httpClient != null ? httpClient : HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
        this.requestUnformatMapper = requestUnformatMapper != null ? requestUnformatMapper : new GetClientLinksRequestUnformatMapper();
        this.successMapper = successMapper != null ? successMapper : new GetClientLinksRSFmtMapper();
        this.errorMapper = errorMapper != null ? errorMapper : new StandardErrorRSFmtMapper();
    }

    public void setContext(OperationContextBridge context) {
        this.context = Objects.requireNonNull(context, "Operation context");
    }

    public OperationContextBridge getContext() {
        if (context == null) {
            throw new IllegalStateException("Configure an operation context before executing a step");
        }
        return context;
    }

    public int execute() throws Exception {
        Object clientIdObj = getContext().getValueAt("ClientId");
        Object bankIdObj = getContext().getValueAt("BankId");
        String clientId = clientIdObj != null ? clientIdObj.toString() : null;
        String bankId = bankIdObj != null ? bankIdObj.toString() : null;

        GetClientLinksRequestXml requestXmlObj = new GetClientLinksRequestXml();
        requestXmlObj.clientId = clientId;
        requestXmlObj.bankId = bankId;

        GetClientLinksRequest requestDto = requestUnformatMapper.toBusinessInput(requestXmlObj);

        XmlMapper xmlMapper = new XmlMapper();
        String requestBody = xmlMapper.writeValueAsString(requestXmlObj);

        String endpoint = baseUrl.replaceAll("/$", "") + "/operations/INTERNET/GetClientLinksOp";
        HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(endpoint))
                .header("Content-Type", "application/xml")
                .header("Accept", "application/xml")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .timeout(Duration.ofSeconds(30))
                .build();

        HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
        int statusCode = response.statusCode();
        String responseBody = response.body();

        if (statusCode >= 200 && statusCode < 300) {
            var successResp = successMapper.unformat(responseBody);
            getContext().setValueAt("GetClientLinksResponse", successResp);
            getContext().setValueAt("ERROR_CODE", "0");
            return 0;
        } else {
            try {
                var errorResp = errorMapper.unformat(responseBody);
                getContext().setValueAt("ErrorReply", errorResp);
                getContext().setValueAt("ERROR_CODE", errorResp.errorNumber() != null ? errorResp.errorNumber() : String.valueOf(statusCode));
            } catch (Exception e) {
                getContext().setValueAt("ERROR_CODE", String.valueOf(statusCode));
            }
            return -1;
        }
    }
}