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
import com.company.generated.units.uf2c8754a25a6.FraudCheckStep;
import com.company.generated.units.udb5b1a29f676.ValidateTransferStep;

import org.junit.jupiter.api.Test;
import java.sql.Connection;
import java.util.Map;

import javax.sql.DataSource;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class Route8c66a266dc97Test {

    @Test
    void testExecuteTransferAlreadyProcessedRouting() throws Exception {
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
        when(checkLimits.execute(any(Map.class))).thenReturn(0);
        when(fraudCheck.execute(any(Map.class))).thenReturn(0);
        when(executeTransfer.execute(any(Map.class))).thenReturn(7);
        when(transferAlreadyProcessed.execute(any(Map.class))).thenReturn(0);

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

        TransferFundsRequestXml requestXml = new TransferFundsRequestXml();
        requestXml.sourceAccount = "ACC-123";
        requestXml.targetAccount = "ACC-456";
        requestXml.amount = "100.00";
        requestXml.currency = "USD";
        requestXml.sessionToken = "tok-111";
        requestXml.transferReference = "ref-dup";
        requestXml.scheduledDate = "2023-10-01";

        String result = service.execute(requestXml);

        assertNotNull(result);
        verify(validateTransfer).execute(any(Map.class));
        verify(checkLimits).execute(any(Map.class));
        verify(fraudCheck).execute(any(Map.class));
        verify(executeTransfer).execute(any(Map.class));
        verify(transferAlreadyProcessed).execute(any(Map.class));
        verifyNoInteractions(coreBankingRejected, dailyLimitExceeded, fraudSuspected, validationFailed, insufficientFunds, accountNotEligible, technicalError, databaseError);
    }
}
