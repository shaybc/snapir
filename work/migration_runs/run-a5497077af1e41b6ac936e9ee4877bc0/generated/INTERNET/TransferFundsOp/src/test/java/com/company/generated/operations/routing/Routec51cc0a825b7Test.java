package com.company.generated.operations.routing;

import com.company.generated.operations.TransferFundsOpService;
import com.company.generated.units.u06cdcaacb2a8.CoreBankingRejectedStep;
import com.company.generated.units.u1bde9d232fc4.DailyLimitExceededStep;
import com.company.generated.units.u1e4c733765f0.AccountNotEligibleStep;
import com.company.generated.units.u2e52a65fe1ce.ValidationFailedStep;
import com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;
import com.company.generated.units.u3edad4d894ed.SkipFraudOnTimeoutStep;
import com.company.generated.units.u4ef069d52e8c.CheckLimitsStep;
import com.company.generated.units.u5ce9c9ef500c.TransferFundsRequestXml;
import com.company.generated.units.u6d24746bc47a.ExecuteTransferStep;
import com.company.generated.units.u87dd336469df.InsufficientFundsStep;
import com.company.generated.units.u90e3461e522a.FraudSuspectedStep;
import com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;
import com.company.generated.units.ub9a6a73909a9.TransferAlreadyProcessedStep;
import com.company.generated.units.udb5b1a29f676.ValidateTransferStep;
import com.company.generated.units.uf2c8754a25a6.FraudCheckStep;

import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.sql.Connection;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class Routec51cc0a825b7Test {

    @Test
    void checkLimitsTechnicalErrorRoutesAndReturnsErrorReply() throws Exception {
        CoreBankingRejectedStep coreBankingRejected = mock(CoreBankingRejectedStep.class);
        SkipFraudOnTimeoutStep skipFraudOnTimeout = mock(SkipFraudOnTimeoutStep.class);
        ExecuteTransferStep executeTransfer = mock(ExecuteTransferStep.class);
        DailyLimitExceededStep dailyLimitExceeded = mock(DailyLimitExceededStep.class);
        TransferAlreadyProcessedStep transferAlreadyProcessed = mock(TransferAlreadyProcessedStep.class);
        FraudCheckStep fraudCheck = mock(FraudCheckStep.class);
        FraudSuspectedStep fraudSuspected = mock(FraudSuspectedStep.class);
        ValidationFailedStep validationFailed = mock(ValidationFailedStep.class);
        InsufficientFundsStep insufficientFunds = mock(InsufficientFundsStep.class);
        ValidateTransferStep validateTransfer = mock(ValidateTransferStep.class);
        AccountNotEligibleStep accountNotEligible = mock(AccountNotEligibleStep.class);
        TechnicalErrorStep technicalError = mock(TechnicalErrorStep.class);
        CheckLimitsStep checkLimits = mock(CheckLimitsStep.class);
        DatabaseErrorStep databaseError = mock(DatabaseErrorStep.class);
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);

        when(dataSource.getConnection()).thenReturn(connection);
        when(validateTransfer.execute(any(Map.class))).thenReturn(0);
        when(checkLimits.execute(any(Map.class))).thenReturn(-1);
        
        doAnswer(invocation -> {
            Map<String, Object> ctx = invocation.getArgument(0);
            ctx.put("ErrorCategory", "99");
            ctx.put("ErrorNumber", "0");
            ctx.put("ErrorDescription", "Technical error");
            return 0;
        }).when(technicalError).execute(any(Map.class));

        TransferFundsRequestXml requestXml = new TransferFundsRequestXml();
        requestXml.sourceAccount = "123456789";
        requestXml.targetAccount = "987654321";
        requestXml.amount = "100.00";
        requestXml.currency = "USD";
        requestXml.sessionToken = "token123";
        requestXml.transferReference = "ref123";

        TransferFundsOpService service = new TransferFundsOpService(
                coreBankingRejected,
                skipFraudOnTimeout,
                executeTransfer,
                dailyLimitExceeded,
                transferAlreadyProcessed,
                fraudCheck,
                fraudSuspected,
                validationFailed,
                insufficientFunds,
                validateTransfer,
                accountNotEligible,
                technicalError,
                checkLimits,
                databaseError,
                dataSource
        );

        String result = service.execute(requestXml);

        verify(validateTransfer).execute(any(Map.class));
        verify(checkLimits).execute(any(Map.class));
        verify(technicalError).execute(any(Map.class));
        assertTrue(result != null && (result.contains("ErrorReply") || result.contains("errorNumber") || result.contains("errorCategory")));
    }
}
