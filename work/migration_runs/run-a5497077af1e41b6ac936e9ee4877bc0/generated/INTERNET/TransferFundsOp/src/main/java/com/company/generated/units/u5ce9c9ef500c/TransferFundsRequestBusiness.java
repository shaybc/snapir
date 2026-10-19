package com.company.generated.units.u5ce9c9ef500c;

import java.math.BigDecimal;

public class TransferFundsRequestBusiness {
    private String sourceAccount;
    private String targetAccount;
    private BigDecimal amount;
    private String currency;
    private String sessionToken;
    private String transferReference;
    private String scheduledDate;

    public String getSourceAccount() { return sourceAccount; }
    public void setSourceAccount(String sourceAccount) { this.sourceAccount = sourceAccount; }

    public String getTargetAccount() { return targetAccount; }
    public void setTargetAccount(String targetAccount) { this.targetAccount = targetAccount; }

    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }

    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }

    public String getSessionToken() { return sessionToken; }
    public void setSessionToken(String sessionToken) { this.sessionToken = sessionToken; }

    public String getTransferReference() { return transferReference; }
    public void setTransferReference(String transferReference) { this.transferReference = transferReference; }

    public String getScheduledDate() { return scheduledDate; }
    public void setScheduledDate(String scheduledDate) { this.scheduledDate = scheduledDate; }
}