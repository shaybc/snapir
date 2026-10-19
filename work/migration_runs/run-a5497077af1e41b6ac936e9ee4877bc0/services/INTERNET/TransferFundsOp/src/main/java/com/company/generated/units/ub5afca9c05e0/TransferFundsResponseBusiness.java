package com.company.generated.units.ub5afca9c05e0;

import java.math.BigDecimal;
import java.util.Date;

public class TransferFundsResponseBusiness {
    private String transferId;
    private String transferStatus;
    private Date executionDate;
    private Date executionTime;
    private BigDecimal amount;
    private String currency;
    private String sourceAccount;
    private String targetAccount;
    private BigDecimal newSourceBalance;
    private Boolean fraudCheckSkipped;

    public TransferFundsResponseBusiness() {}

    public String getTransferId() { return transferId; }
    public void setTransferId(String transferId) { this.transferId = transferId; }

    public String getTransferStatus() { return transferStatus; }
    public void setTransferStatus(String transferStatus) { this.transferStatus = transferStatus; }

    public Date getExecutionDate() { return executionDate; }
    public void setExecutionDate(Date executionDate) { this.executionDate = executionDate; }

    public Date getExecutionTime() { return executionTime; }
    public void setExecutionTime(Date executionTime) { this.executionTime = executionTime; }

    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }

    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }

    public String getSourceAccount() { return sourceAccount; }
    public void setSourceAccount(String sourceAccount) { this.sourceAccount = sourceAccount; }

    public String getTargetAccount() { return targetAccount; }
    public void setTargetAccount(String targetAccount) { this.targetAccount = targetAccount; }

    public BigDecimal getNewSourceBalance() { return newSourceBalance; }
    public void setNewSourceBalance(BigDecimal newSourceBalance) { this.newSourceBalance = newSourceBalance; }

    public Boolean getFraudCheckSkipped() { return fraudCheckSkipped; }
    public void setFraudCheckSkipped(Boolean fraudCheckSkipped) { this.fraudCheckSkipped = fraudCheckSkipped; }
}
