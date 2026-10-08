package com.company.generated;

import jakarta.xml.bind.annotation.XmlElement;
import jakarta.xml.bind.annotation.XmlRootElement;

@XmlRootElement(name = "TransferFundsResponse")
public class TransferFundsRSFmtDto {

    private String transferId;
    private String transferStatus;
    private String executionDate;
    private String executionTime;
    private String amount;
    private String currency;
    private String sourceAccount;
    private String targetAccount;
    private String newSourceBalance;
    private boolean fraudCheckSkipped;

    public TransferFundsRSFmtDto() {
    }

    @XmlElement(name = "TransferId")
    public String getTransferId() {
        return transferId;
    }

    public void setTransferId(String transferId) {
        this.transferId = transferId;
    }

    @XmlElement(name = "TransferStatus")
    public String getTransferStatus() {
        return transferStatus;
    }

    public void setTransferStatus(String transferStatus) {
        this.transferStatus = transferStatus;
    }

    @XmlElement(name = "ExecutionDate")
    public String getExecutionDate() {
        return executionDate;
    }

    public void setExecutionDate(String executionDate) {
        this.executionDate = executionDate;
    }

    @XmlElement(name = "ExecutionTime")
    public String getExecutionTime() {
        return executionTime;
    }

    public void setExecutionTime(String executionTime) {
        this.executionTime = executionTime;
    }

    @XmlElement(name = "Amount")
    public String getAmount() {
        return amount;
    }

    public void setAmount(String amount) {
        this.amount = amount;
    }

    @XmlElement(name = "Currency")
    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    @XmlElement(name = "SourceAccount")
    public String getSourceAccount() {
        return sourceAccount;
    }

    public void setSourceAccount(String sourceAccount) {
        this.sourceAccount = sourceAccount;
    }

    @XmlElement(name = "TargetAccount")
    public String getTargetAccount() {
        return targetAccount;
    }

    public void setTargetAccount(String targetAccount) {
        this.targetAccount = targetAccount;
    }

    @XmlElement(name = "NewSourceBalance")
    public String getNewSourceBalance() {
        return newSourceBalance;
    }

    public void setNewSourceBalance(String newSourceBalance) {
        this.newSourceBalance = newSourceBalance;
    }

    @XmlElement(name = "FraudCheckSkipped")
    public boolean isFraudCheckSkipped() {
        return fraudCheckSkipped;
    }

    public void setFraudCheckSkipped(boolean fraudCheckSkipped) {
        this.fraudCheckSkipped = fraudCheckSkipped;
    }
}