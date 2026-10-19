package com.company.generated.units.u5ce9c9ef500c;

import java.math.BigDecimal;

public class TransferFundsRequestMapper {
    public TransferFundsRequestBusiness toBusinessInput(TransferFundsRequestXml wire) {
        if (wire == null) {
            return null;
        }
        TransferFundsRequestBusiness biz = new TransferFundsRequestBusiness();
        biz.setSourceAccount(removePadding(wire.sourceAccount, '0', 10, true));
        biz.setTargetAccount(removePadding(wire.targetAccount, '0', 10, true));
        
        if (wire.amount != null && !wire.amount.isBlank()) {
            String cleanAmount = wire.amount.replace(",", "").trim();
            biz.setAmount(new BigDecimal(cleanAmount));
        } else {
            biz.setAmount(null);
        }

        biz.setCurrency(removeRightPadding(wire.currency, ' ', 3));
        biz.setSessionToken(wire.sessionToken);
        biz.setTransferReference(wire.transferReference);
        biz.setScheduledDate(wire.scheduledDate);
        return biz;
    }

    private String removePadding(String value, char padChar, int length, boolean padLeft) {
        if (value == null) {
            return null;
        }
        String res = value;
        if (padLeft) {
            res = res.replaceFirst("^[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+", "");
        } else {
            res = res.replaceFirst("[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+$", "");
        }
        return res;
    }

    private String removeRightPadding(String value, char padChar, int length) {
        if (value == null) {
            return null;
        }
        return value.replaceFirst("[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+$", "");
    }
}