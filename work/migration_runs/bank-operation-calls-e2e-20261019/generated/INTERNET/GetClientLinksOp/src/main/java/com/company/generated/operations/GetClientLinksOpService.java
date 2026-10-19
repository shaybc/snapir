package com.company.generated.operations;

import com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;
import com.company.generated.units.u3a42c4326e3d.OperationContext;
import com.company.generated.units.u3643d2141e0a.NoLinksFoundStep;
import com.company.generated.units.u42b95631a186.GetClientLinksStep;
import com.company.generated.units.u561a01497abb.GetClientLinksRequest;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestUnformatMapper;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;

import javax.sql.DataSource;
import java.sql.Connection;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class GetClientLinksOpService {

    private final GetClientLinksStep getClientLinksStep;
    private final NoLinksFoundStep noLinksFoundStep;
    private final DatabaseErrorStep databaseErrorStep;
    private final TechnicalErrorStep technicalError;
    private final DataSource dataSource;

    private final GetClientLinksRequestUnformatMapper requestUnformatMapper;
    private final GetClientLinksRSFmtMapper replyFormatMapper;
    private final StandardErrorRSFmtMapper errorReplyFormatMapper;

    public GetClientLinksOpService(
            GetClientLinksStep getClientLinksStep,
            NoLinksFoundStep noLinksFoundStep,
            DatabaseErrorStep databaseErrorStep,
            TechnicalErrorStep technicalError,
            DataSource dataSource) {
        this.getClientLinksStep = Objects.requireNonNull(getClientLinksStep);
        this.noLinksFoundStep = Objects.requireNonNull(noLinksFoundStep);
        this.databaseErrorStep = Objects.requireNonNull(databaseErrorStep);
        this.technicalError = Objects.requireNonNull(technicalError);
        this.dataSource = Objects.requireNonNull(dataSource);

        this.requestUnformatMapper = new GetClientLinksRequestUnformatMapper();
        this.replyFormatMapper = new GetClientLinksRSFmtMapper();
        this.errorReplyFormatMapper = new StandardErrorRSFmtMapper();
    }

    public String execute(GetClientLinksRequestXml requestXml) throws Exception {
        GetClientLinksRequest request = requestUnformatMapper.toBusinessInput(requestXml);
        OperationContext context = new OperationContext();
        context.setValueAt("ClientId", request.getClientId());
        context.setValueAt("BankId", request.getBankId());
        context.setValueAt("HOST_HEADER.HOST_KEY", "GCLN");

        int rc;
        try (Connection connection = dataSource.getConnection()) {
            context.setConnection(connection);
            rc = getClientLinksStep.execute(context);
        }

        if (rc == 0) {
            String clientId = (String) context.getValueAt("ClientId");
            List<Object> rawLinks = (List<Object>) context.getValueAt("Links");
            List<GetClientLinksRSFmtMapper.LinkDto> linkDtos = new java.util.ArrayList<>();

            if (rawLinks != null) {
                for (Object rawLink : rawLinks) {
                    if (rawLink instanceof Map) {
                        Map<?, ?> map = (Map<?, ?>) rawLink;
                        String linkId = (String) map.get("LinkId");
                        String linkDescription = (String) map.get("LinkDescription");
                        String linkUrl = (String) map.get("LinkUrl");
                        Boolean isExternal = (Boolean) map.get("IsExternal");
                        String iconCode = (String) map.get("IconCode");
                        linkDtos.add(new GetClientLinksRSFmtMapper.LinkDto(linkId, linkDescription, linkUrl, isExternal, iconCode));
                    }
                }
            }

            GetClientLinksRSFmtMapper.GetClientLinksResponse response = 
                new GetClientLinksRSFmtMapper.GetClientLinksResponse(clientId, linkDtos);
            return replyFormatMapper.format(response);
        } else {
            String errorCategory;
            String errorNumber;
            String errorDescription;

            if (rc == 4) {
                noLinksFoundStep.execute(context);
                errorCategory = noLinksFoundStep.getErrorCategory();
                errorNumber = noLinksFoundStep.getErrorNumber();
            } else if (rc == 8) {
                databaseErrorStep.execute(context);
                errorCategory = databaseErrorStep.getErrorCategory();
                errorNumber = databaseErrorStep.getErrorNumber();
            } else {
                technicalError.execute(context);
                errorCategory = technicalError.getErrorCategory();
                errorNumber = technicalError.getErrorNumber();
            }

            errorDescription = (String) context.getValueAt("ErrorDescription");
            String requestId = (String) context.getValueAt("RequestId");

            StandardErrorRSFmtMapper.ErrorReply errorReply = 
                new StandardErrorRSFmtMapper.ErrorReply(errorCategory, errorNumber, errorDescription, requestId);
            return errorReplyFormatMapper.format(errorReply);
        }
    }
}
