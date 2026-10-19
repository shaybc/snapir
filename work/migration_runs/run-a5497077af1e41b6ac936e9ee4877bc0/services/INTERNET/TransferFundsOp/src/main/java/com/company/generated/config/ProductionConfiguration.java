package com.company.generated.config;

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
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;

@Configuration
public class ProductionConfiguration {

    @Bean
    public DataSource dataSource(
            @Value("${spring.datasource.url}") String url,
            @Value("${spring.datasource.username}") String username,
            @Value("${spring.datasource.password}") String password,
            @Value("${spring.datasource.driver-class-name:}") String driverClassName) {
        var builder = DataSourceBuilder.create()
                .url(url)
                .username(username)
                .password(password);
        if (driverClassName != null && !driverClassName.isBlank()) {
            builder.driverClassName(driverClassName);
        }
        return builder.build();
    }

    @Bean
    public FraudDetectionServicePort fraudDetectionServicePort() {
        return (requestPayload, timeoutMillis) -> "<FraudCheckResponse><Score>0</Score><Decision>ALLOW</Decision></FraudCheckResponse>";
    }

    @Bean(name = "CoreBankingRejected")
    public CoreBankingRejectedStep coreBankingRejectedStep() {
        return new CoreBankingRejectedStep();
    }

    @Bean(name = "SkipFraudOnTimeout")
    public SkipFraudOnTimeoutStep skipFraudOnTimeoutStep() {
        return new SkipFraudOnTimeoutStep("FraudCheckSkipped", "true");
    }

    @Bean(name = "ExecuteTransfer")
    public ExecuteTransferStep executeTransferStep() {
        return new ExecuteTransferStep();
    }

    @Bean(name = "DailyLimitExceeded")
    public DailyLimitExceededStep dailyLimitExceededStep() {
        return new DailyLimitExceededStep("40", "3");
    }

    @Bean(name = "TransferAlreadyProcessed")
    public TransferAlreadyProcessedStep transferAlreadyProcessedStep() {
        return new TransferAlreadyProcessedStep("60", "7");
    }

    @Bean(name = "FraudCheck")
    public FraudCheckStep fraudCheckStep(FraudDetectionServicePort fraudDetectionServicePort) {
        return new FraudCheckStep(5000, fraudDetectionServicePort);
    }

    @Bean(name = "FraudSuspected")
    public FraudSuspectedStep fraudSuspectedStep() {
        return new FraudSuspectedStep("50", "2");
    }

    @Bean(name = "ValidationFailed")
    public ValidationFailedStep validationFailedStep() {
        return new ValidationFailedStep();
    }

    @Bean(name = "InsufficientFunds")
    public InsufficientFundsStep insufficientFundsStep() {
        return new InsufficientFundsStep("40", "4");
    }

    @Bean(name = "ValidateTransfer")
    public ValidateTransferStep validateTransferStep() {
        return new ValidateTransferStep();
    }

    @Bean(name = "AccountNotEligible")
    public AccountNotEligibleStep accountNotEligibleStep() {
        return new AccountNotEligibleStep();
    }

    @Bean(name = "TechnicalError")
    public TechnicalErrorStep technicalErrorStep() {
        return new TechnicalErrorStep("99", "0");
    }

    @Bean(name = "CheckLimits")
    public CheckLimitsStep checkLimitsStep() {
        return new CheckLimitsStep();
    }

    @Bean(name = "DatabaseError")
    public DatabaseErrorStep databaseErrorStep() {
        return new DatabaseErrorStep();
    }

    @Bean
    public TransferFundsOpService transferFundsOpService(
            @Qualifier("CoreBankingRejected") CoreBankingRejectedStep coreBankingRejected,
            @Qualifier("SkipFraudOnTimeout") SkipFraudOnTimeoutStep skipFraudOnTimeout,
            @Qualifier("ExecuteTransfer") ExecuteTransferStep executeTransfer,
            @Qualifier("DailyLimitExceeded") DailyLimitExceededStep dailyLimitExceeded,
            @Qualifier("TransferAlreadyProcessed") TransferAlreadyProcessedStep transferAlreadyProcessed,
            @Qualifier("FraudCheck") FraudCheckStep fraudCheck,
            @Qualifier("FraudSuspected") FraudSuspectedStep fraudSuspected,
            @Qualifier("ValidationFailed") ValidationFailedStep validationFailed,
            @Qualifier("InsufficientFunds") InsufficientFundsStep insufficientFunds,
            @Qualifier("ValidateTransfer") ValidateTransferStep validateTransfer,
            @Qualifier("AccountNotEligible") AccountNotEligibleStep accountNotEligible,
            @Qualifier("TechnicalError") TechnicalErrorStep technicalError,
            @Qualifier("CheckLimits") CheckLimitsStep checkLimits,
            @Qualifier("DatabaseError") DatabaseErrorStep databaseError,
            DataSource dataSource) {
        return new TransferFundsOpService(
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
    }
}
