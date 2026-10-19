package com.company.generated.wiring;

import com.company.generated.config.ProductionConfiguration;
import com.company.generated.operations.TransferFundsOpService;
import com.company.generated.units.u06cdcaacb2a8.CoreBankingRejectedStep;
import com.company.generated.units.u1bde9d232fc4.DailyLimitExceededStep;
import com.company.generated.units.u1e4c733765f0.AccountNotEligibleStep;
import com.company.generated.units.u2e52a65fe1ce.ValidationFailedStep;
import com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;
import com.company.generated.units.u3edad4d894ed.SkipFraudOnTimeoutStep;
import com.company.generated.units.u4ef069d52e8c.CheckLimitsStep;
import com.company.generated.units.u6d24746bc47a.ExecuteTransferStep;
import com.company.generated.units.u87dd336469df.InsufficientFundsStep;
import com.company.generated.units.u90e3461e522a.FraudSuspectedStep;
import com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;
import com.company.generated.units.ub9a6a73909a9.TransferAlreadyProcessedStep;
import com.company.generated.units.udb5b1a29f676.ValidateTransferStep;
import com.company.generated.units.uf2c8754a25a6.FraudCheckStep;
import com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import javax.sql.DataSource;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class StartupWiringTest {

    @Test
    void testProductionWiringStartup() {
        try (var context = new AnnotationConfigApplicationContext()) {
            context.addBeanFactoryPostProcessor(factory -> {
                factory.registerSingleton("dataSource", Mockito.mock(DataSource.class));
                factory.registerSingleton("fraudDetectionServicePort", Mockito.mock(FraudDetectionServicePort.class));
            });
            context.register(ProductionConfiguration.class);
            context.refresh();

            var service = context.getBean(TransferFundsOpService.class);
            assertFalse(Mockito.mockingDetails(service).isMock());
            assertNotNull(service);

            var coreBankingRejected = context.getBean("CoreBankingRejected", CoreBankingRejectedStep.class);
            assertFalse(Mockito.mockingDetails(coreBankingRejected).isMock());

            var skipFraudOnTimeout = context.getBean("SkipFraudOnTimeout", SkipFraudOnTimeoutStep.class);
            assertFalse(Mockito.mockingDetails(skipFraudOnTimeout).isMock());

            var executeTransfer = context.getBean("ExecuteTransfer", ExecuteTransferStep.class);
            assertFalse(Mockito.mockingDetails(executeTransfer).isMock());

            var dailyLimitExceeded = context.getBean("DailyLimitExceeded", DailyLimitExceededStep.class);
            assertFalse(Mockito.mockingDetails(dailyLimitExceeded).isMock());

            var transferAlreadyProcessed = context.getBean("TransferAlreadyProcessed", TransferAlreadyProcessedStep.class);
            assertFalse(Mockito.mockingDetails(transferAlreadyProcessed).isMock());

            var fraudCheck = context.getBean("FraudCheck", FraudCheckStep.class);
            assertFalse(Mockito.mockingDetails(fraudCheck).isMock());

            var fraudSuspected = context.getBean("FraudSuspected", FraudSuspectedStep.class);
            assertFalse(Mockito.mockingDetails(fraudSuspected).isMock());

            var validationFailed = context.getBean("ValidationFailed", ValidationFailedStep.class);
            assertFalse(Mockito.mockingDetails(validationFailed).isMock());

            var insufficientFunds = context.getBean("InsufficientFunds", InsufficientFundsStep.class);
            assertFalse(Mockito.mockingDetails(insufficientFunds).isMock());

            var validateTransfer = context.getBean("ValidateTransfer", ValidateTransferStep.class);
            assertFalse(Mockito.mockingDetails(validateTransfer).isMock());

            var accountNotEligible = context.getBean("AccountNotEligible", AccountNotEligibleStep.class);
            assertFalse(Mockito.mockingDetails(accountNotEligible).isMock());

            var technicalError = context.getBean("TechnicalError", TechnicalErrorStep.class);
            assertFalse(Mockito.mockingDetails(technicalError).isMock());

            var checkLimits = context.getBean("CheckLimits", CheckLimitsStep.class);
            assertFalse(Mockito.mockingDetails(checkLimits).isMock());

            var databaseError = context.getBean("DatabaseError", DatabaseErrorStep.class);
            assertFalse(Mockito.mockingDetails(databaseError).isMock());
        }
    }
}
