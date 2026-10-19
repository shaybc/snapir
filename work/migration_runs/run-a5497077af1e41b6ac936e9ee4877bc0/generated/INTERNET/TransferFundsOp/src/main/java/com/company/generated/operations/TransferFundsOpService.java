package com.company.generated.operations;

import com.company.generated.units.u06cdcaacb2a8.CoreBankingRejectedStep;
import com.company.generated.units.u1bde9d232fc4.DailyLimitExceededStep;
import com.company.generated.units.u1e4c733765f0.AccountNotEligibleStep;
import com.company.generated.units.u2e52a65fe1ce.ValidationFailedStep;
import com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;
import com.company.generated.units.u3edad4d894ed.SkipFraudOnTimeoutStep;
import com.company.generated.units.u4ef069d52e8c.CheckLimitsStep;
import com.company.generated.units.u5ce9c9ef500c.TransferFundsRequestBusiness;
import com.company.generated.units.u5ce9c9ef500c.TransferFundsRequestMapper;
import com.company.generated.units.u5ce9c9ef500c.TransferFundsRequestXml;
import com.company.generated.units.u66bf2c108225.ErrorReply;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import com.company.generated.units.u6d24746bc47a.ExecuteTransferStep;
import com.company.generated.units.u87dd336469df.InsufficientFundsStep;
import com.company.generated.units.u90e3461e522a.FraudSuspectedStep;
import com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;
import com.company.generated.units.ub5afca9c05e0.TransferFundsResponseBusiness;
import com.company.generated.units.ub5afca9c05e0.TransferFundsResponseMapper;
import com.company.generated.units.ub9a6a73909a9.TransferAlreadyProcessedStep;
import com.company.generated.units.uf2c8754a25a6.FraudCheckStep;
import com.company.generated.units.udb5b1a29f676.ValidateTransferStep;

import javax.sql.DataSource;
import java.math.BigDecimal;
import java.sql.Connection;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public class TransferFundsOpService {

    private final CoreBankingRejectedStep coreBankingRejected;
    private final SkipFraudOnTimeoutStep skipFraudOnTimeout;
    private final ExecuteTransferStep executeTransfer;
    private final DailyLimitExceededStep dailyLimitExceeded;
    private final TransferAlreadyProcessedStep transferAlreadyProcessed;
    private final FraudCheckStep fraudCheck;
    private final FraudSuspectedStep fraudSuspected;
    private final ValidationFailedStep validationFailed;
    private final InsufficientFundsStep insufficientFunds;
    private final ValidateTransferStep validateTransfer;
    private final AccountNotEligibleStep accountNotEligible;
    private final TechnicalErrorStep technicalError;
    private final CheckLimitsStep checkLimits;
    private final DatabaseErrorStep databaseError;
    private final DataSource dataSource;

    private final TransferFundsRequestMapper requestMapper = new TransferFundsRequestMapper();
    private final TransferFundsResponseMapper responseMapper = new TransferFundsResponseMapper();
    private final StandardErrorRSFmtMapper errorMapper = new StandardErrorRSFmtMapper();

    public TransferFundsOpService(
            CoreBankingRejectedStep coreBankingRejected,
            SkipFraudOnTimeoutStep skipFraudOnTimeout,
            ExecuteTransferStep executeTransfer,
            DailyLimitExceededStep dailyLimitExceeded,
            TransferAlreadyProcessedStep transferAlreadyProcessed,
            FraudCheckStep fraudCheck,
            FraudSuspectedStep fraudSuspected,
            ValidationFailedStep validationFailed,
            InsufficientFundsStep insufficientFunds,
            ValidateTransferStep validateTransfer,
            AccountNotEligibleStep accountNotEligible,
            TechnicalErrorStep technicalError,
            CheckLimitsStep checkLimits,
            DatabaseErrorStep databaseError,
            DataSource dataSource) {
        this.coreBankingRejected = Objects.requireNonNull(coreBankingRejected);
        this.skipFraudOnTimeout = Objects.requireNonNull(skipFraudOnTimeout);
        this.executeTransfer = Objects.requireNonNull(executeTransfer);
        this.dailyLimitExceeded = Objects.requireNonNull(dailyLimitExceeded);
        this.transferAlreadyProcessed = Objects.requireNonNull(transferAlreadyProcessed);
        this.fraudCheck = Objects.requireNonNull(fraudCheck);
        this.fraudSuspected = Objects.requireNonNull(fraudSuspected);
        this.validationFailed = Objects.requireNonNull(validationFailed);
        this.insufficientFunds = Objects.requireNonNull(insufficientFunds);
        this.validateTransfer = Objects.requireNonNull(validateTransfer);
        this.accountNotEligible = Objects.requireNonNull(accountNotEligible);
        this.technicalError = Objects.requireNonNull(technicalError);
        this.checkLimits = Objects.requireNonNull(checkLimits);
        this.databaseError = Objects.requireNonNull(databaseError);
        this.dataSource = Objects.requireNonNull(dataSource);
    }

    public String execute(TransferFundsRequestXml requestXml) throws Exception {
        TransferFundsRequestBusiness reqBiz = requestMapper.toBusinessInput(requestXml);

        Map<String, Object> context = new HashMap<>();
        context.put("CHANNEL_ID", "INTERNET");
        context.put("MAX_RETRY", "3");
        context.put("TransferStatus", "PENDING");
        context.put("FraudScore", "0");

        if (reqBiz != null) {
            context.put("SourceAccount", reqBiz.getSourceAccount());
            context.put("TargetAccount", reqBiz.getTargetAccount());
            context.put("Amount", reqBiz.getAmount());
            context.put("Currency", reqBiz.getCurrency());
            context.put("SessionToken", reqBiz.getSessionToken());
            context.put("TransferReference", reqBiz.getTransferReference());
            context.put("ScheduledDate", reqBiz.getScheduledDate());
        }

        try (Connection connection = dataSource.getConnection()) {
            context.put("Connection", connection);

            String currentStep = "ValidateTransfer";
            int rc;

            while (currentStep != null && !currentStep.equals("end")) {
                switch (currentStep) {
                    case "ValidateTransfer":
                        rc = validateTransfer.execute(context);
                        if (rc == 0) {
                            currentStep = "CheckLimits";
                        } else {
                            currentStep = "ValidationFailed";
                        }
                        break;

                    case "CheckLimits":
                        rc = checkLimits.execute(context);
                        if (rc == 0) {
                            currentStep = "FraudCheck";
                        } else if (rc == 3) {
                            currentStep = "DailyLimitExceeded";
                        } else if (rc == 4) {
                            currentStep = "InsufficientFunds";
                        } else if (rc == 5) {
                            currentStep = "AccountNotEligible";
                        } else if (rc == 8) {
                            currentStep = "DatabaseError";
                        } else {
                            currentStep = "TechnicalError";
                        }
                        break;

                    case "FraudCheck":
                        try {
                            rc = fraudCheck.execute(context);
                            if (rc == 0) {
                                currentStep = "ExecuteTransfer";
                            } else if (rc == 2) {
                                currentStep = "FraudSuspected";
                            } else {
                                currentStep = "TechnicalError";
                            }
                        } catch (java.util.concurrent.TimeoutException | java.util.concurrent.CancellationException e) {
                            rc = skipFraudOnTimeout.execute(context);
                            if (rc == 0) {
                                currentStep = "ExecuteTransfer";
                            } else {
                                currentStep = "TechnicalError";
                            }
                        } catch (Exception e) {
                            rc = skipFraudOnTimeout.execute(context);
                            if (rc == 0) {
                                currentStep = "ExecuteTransfer";
                            } else {
                                currentStep = "TechnicalError";
                            }
                        }
                        break;

                    case "SkipFraudOnTimeout":
                        rc = skipFraudOnTimeout.execute(context);
                        if (rc == 0) {
                            currentStep = "ExecuteTransfer";
                        } else {
                            currentStep = "TechnicalError";
                        }
                        break;

                    case "ExecuteTransfer":
                        rc = executeTransfer.execute(context);
                        if (rc == 0) {
                            currentStep = "end";
                        } else if (rc == 6) {
                            currentStep = "CoreBankingRejected";
                        } else if (rc == 7) {
                            currentStep = "TransferAlreadyProcessed";
                        } else if (rc == 8) {
                            currentStep = "DatabaseError";
                        } else {
                            currentStep = "TechnicalError";
                        }
                        break;

                    case "ValidationFailed":
                        validationFailed.execute(context);
                        currentStep = "end";
                        break;

                    case "InsufficientFunds":
                        insufficientFunds.execute(context);
                        currentStep = "end";
                        break;

                    case "DailyLimitExceeded":
                        dailyLimitExceeded.execute(context);
                        currentStep = "end";
                        break;

                    case "AccountNotEligible":
                        accountNotEligible.execute(context);
                        currentStep = "end";
                        break;

                    case "FraudSuspected":
                        fraudSuspected.execute(context);
                        currentStep = "end";
                        break;

                    case "CoreBankingRejected":
                        coreBankingRejected.execute(context);
                        currentStep = "end";
                        break;

                    case "TransferAlreadyProcessed":
                        transferAlreadyProcessed.execute(context);
                        currentStep = "end";
                        break;

                    case "DatabaseError":
                        databaseError.execute(context);
                        currentStep = "end";
                        break;

                    case "TechnicalError":
                        technicalError.execute(context);
                        currentStep = "end";
                        break;

                    default:
                        currentStep = "end";
                        break;
                }
            }

            if (context.containsKey("ErrorCategory") || context.containsKey("ErrorReply")) {
                ErrorReply errorReply = new ErrorReply(
                    (String) context.getOrDefault("ErrorCategory", "ERR"),
                    (String) context.getOrDefault("ErrorNumber", "500"),
                    (String) context.getOrDefault("ErrorDescription", "Technical Error"),
                    (String) context.getOrDefault("RequestId", "REQ-001")
                );
                return errorMapper.format(errorReply);
            } else {
                TransferFundsResponseBusiness respBiz = new TransferFundsResponseBusiness();
                respBiz.setTransferId((String) context.get("TransferId"));
                respBiz.setTransferStatus((String) context.get("TransferStatus"));
                Object execDate = context.get("ExecutionDate");
                if (execDate instanceof java.util.Date) {
                    respBiz.setExecutionDate((java.util.Date) execDate);
                } else if (execDate instanceof java.time.LocalDate) {
                    respBiz.setExecutionDate(java.sql.Date.valueOf((java.time.LocalDate) execDate));
                }
                Object execTime = context.get("ExecutionTime");
                if (execTime instanceof java.util.Date) {
                    respBiz.setExecutionTime((java.util.Date) execTime);
                }
                respBiz.setAmount((BigDecimal) context.get("Amount"));
                respBiz.setCurrency((String) context.get("Currency"));
                respBiz.setSourceAccount((String) context.get("SourceAccount"));
                respBiz.setTargetAccount((String) context.get("TargetAccount"));
                respBiz.setNewSourceBalance((BigDecimal) context.get("NewSourceBalance"));
                Object fraudSkipped = context.get("FraudCheckSkipped");
                if (fraudSkipped instanceof Boolean) {
                    respBiz.setFraudCheckSkipped((Boolean) fraudSkipped);
                }
                return responseMapper.format(respBiz);
            }
        }
    }
}
