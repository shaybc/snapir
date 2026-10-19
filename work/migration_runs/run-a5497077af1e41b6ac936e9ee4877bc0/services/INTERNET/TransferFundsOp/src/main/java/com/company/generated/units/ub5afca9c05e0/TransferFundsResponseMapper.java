package com.company.generated.units.ub5afca9c05e0;

import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.fasterxml.jackson.dataformat.xml.ser.ToXmlGenerator;

import java.math.BigDecimal;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Objects;

public class TransferFundsResponseMapper {
    private final XmlMapper xmlMapper;

    public TransferFundsResponseMapper() {
        this.xmlMapper = new XmlMapper();
        this.xmlMapper.configure(ToXmlGenerator.Feature.WRITE_XML_DECLARATION, false);
    }

    public String format(TransferFundsResponseBusiness business) throws Exception {
        Objects.requireNonNull(business, "TransferFundsResponseBusiness cannot be null");
        TransferFundsResponseXml wire = new TransferFundsResponseXml();
        wire.transferId = business.getTransferId();
        wire.transferStatus = business.getTransferStatus();

        if (business.getExecutionDate() != null) {
            SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
            wire.executionDate = sdf.format(business.getExecutionDate());
        }

        wire.executionTime = business.getExecutionTime() != null ? "00:00:00" : null;

        if (business.getAmount() != null) {
            wire.amount = business.getAmount().setScale(2).toPlainString();
        }

        wire.currency = business.getCurrency();

        String srcAcc = business.getSourceAccount() != null ? business.getSourceAccount() : "";
        if (srcAcc.length() < 3) {
            srcAcc = " ".repeat(3 - srcAcc.length()) + srcAcc;
        }
        wire.sourceAccount = srcAcc;

        String tgtAcc = business.getTargetAccount() != null ? business.getTargetAccount() : "";
        if (tgtAcc.length() < 10) {
            tgtAcc = "0".repeat(10 - tgtAcc.length()) + tgtAcc;
        }
        wire.targetAccount = tgtAcc;

        if (business.getNewSourceBalance() != null) {
            wire.newSourceBalance = business.getNewSourceBalance().setScale(2).toPlainString();
        } else {
            wire.newSourceBalance = null;
        }

        wire.fraudCheckSkipped = new TransferFundsResponseXml.NullableBoolean();
        if (business.getFraudCheckSkipped() == null) {
            wire.fraudCheckSkipped.nil = "true";
        } else {
            wire.fraudCheckSkipped.value = business.getFraudCheckSkipped().toString();
        }

        return xmlMapper.writeValueAsString(wire);
    }

    public TransferFundsResponseBusiness unformat(String xml) throws Exception {
        TransferFundsResponseXml wire = xmlMapper.readValue(xml, TransferFundsResponseXml.class);
        Objects.requireNonNull(wire, "TransferFundsResponseXml cannot be null");

        TransferFundsResponseBusiness business = new TransferFundsResponseBusiness();
        business.setTransferId(wire.transferId);
        business.setTransferStatus(wire.transferStatus);

        if (wire.executionDate != null && !wire.executionDate.isBlank()) {
            business.setExecutionDate(new SimpleDateFormat("yyyyMMdd").parse(wire.executionDate));
        }

        if (wire.executionTime != null && !wire.executionTime.isBlank()) {
            business.setExecutionTime(new Date(0L));
        }

        if (wire.amount != null && !wire.amount.isBlank()) {
            business.setAmount(new BigDecimal(wire.amount));
        }

        business.setCurrency(wire.currency);

        if (wire.sourceAccount != null) {
            business.setSourceAccount(wire.sourceAccount.replaceFirst("^ +", ""));
        }

        if (wire.targetAccount != null) {
            business.setTargetAccount(wire.targetAccount.replaceFirst("^0+", ""));
        }

        if (wire.newSourceBalance != null && !wire.newSourceBalance.isBlank()) {
            business.setNewSourceBalance(new BigDecimal(wire.newSourceBalance));
        }

        Boolean fraudCheckSkipped = null;
        if (wire.fraudCheckSkipped != null && !"true".equals(wire.fraudCheckSkipped.nil)) {
            fraudCheckSkipped = Boolean.valueOf(wire.fraudCheckSkipped.value);
        }
        business.setFraudCheckSkipped(fraudCheckSkipped);

        return business;
    }
}
