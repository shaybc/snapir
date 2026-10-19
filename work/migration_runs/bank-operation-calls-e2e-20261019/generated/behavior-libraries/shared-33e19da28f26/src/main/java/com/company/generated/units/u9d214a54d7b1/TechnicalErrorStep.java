package com.company.generated.units.u9d214a54d7b1;

import com.company.generated.units.u3a42c4326e3d.OperationContext;
import java.util.Objects;

public class TechnicalErrorStep {
    private final String errorCategory;
    private final String errorNumber;

    public TechnicalErrorStep() {
        this.errorCategory = "99";
        this.errorNumber = "0";
    }

    public TechnicalErrorStep(String errorCategory, String errorNumber) {
        this.errorCategory = errorCategory != null ? errorCategory : "99";
        this.errorNumber = errorNumber != null ? errorNumber : "0";
    }

    public int execute(OperationContext context) {
        Objects.requireNonNull(context, "OperationContext");
        context.setValueAt("ErrorCategory", errorCategory);
        context.setValueAt("ErrorNumber", errorNumber);
        context.setValueAt("ErrorDescription", resolveErrorDescription(errorCategory, errorNumber));
        return 0;
    }

    public String getErrorCategory() {
        return errorCategory;
    }

    public String getErrorNumber() {
        return errorNumber;
    }

    private String resolveErrorDescription(String category, String number) {
        String key = category + "_" + number;
        switch (key) {
            case "10_2": return "Validation failed: required field missing or invalid";
            case "20_1": return "No data found for the provided criteria";
            case "20_4": return "Account not found";
            case "30_5": return "Access denied: insufficient permissions";
            case "40_3": return "Daily transfer limit exceeded";
            case "40_4": return "Insufficient funds";
            case "40_5": return "Account not eligible for this operation";
            case "50_2": return "Transfer blocked: fraud risk detected";
            case "60_6": return "Core banking system rejected the request";
            case "60_7": return "Transfer already processed";
            case "99_0": return "Technical error: unexpected system failure";
            case "99_8": return "Technical error: database connection failure";
            default:     return "System error (category=" + category + ", number=" + number + ")";
        }
    }
}
