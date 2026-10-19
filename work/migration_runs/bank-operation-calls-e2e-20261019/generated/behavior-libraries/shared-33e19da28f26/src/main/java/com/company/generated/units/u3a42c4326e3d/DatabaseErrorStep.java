package com.company.generated.units.u3a42c4326e3d;

import java.util.Objects;

public class DatabaseErrorStep {
    private final String errorCategory;
    private final String errorNumber;

    public DatabaseErrorStep() {
        this.errorCategory = "99";
        this.errorNumber = "8";
    }

    public DatabaseErrorStep(String errorCategory, String errorNumber) {
        this.errorCategory = errorCategory != null ? errorCategory : "99";
        this.errorNumber = errorNumber != null ? errorNumber : "8";
    }

    public int execute(OperationContext context) {
        Objects.requireNonNull(context, "OperationContext");
        context.setValueAt("ErrorCategory", errorCategory);
        context.setValueAt("ErrorNumber", errorNumber);
        context.setValueAt("ErrorDescription", resolveErrorDescription(errorCategory, errorNumber));
        return 0;
    }

    private String resolveErrorDescription(String category, String number) {
        String key = category + "_" + number;
        return switch (key) {
            case "10_2" -> "Validation failed: required field missing or invalid";
            case "20_1" -> "No data found for the provided criteria";
            case "20_4" -> "Account not found";
            case "30_5" -> "Access denied: insufficient permissions";
            case "40_3" -> "Daily transfer limit exceeded";
            case "40_4" -> "Insufficient funds";
            case "40_5" -> "Account not eligible for this operation";
            case "50_2" -> "Transfer blocked: fraud risk detected";
            case "60_6" -> "Core banking system rejected the request";
            case "60_7" -> "Transfer already processed";
            case "99_0" -> "Technical error: unexpected system failure";
            case "99_8" -> "Technical error: database connection failure";
            default -> "System error (category=" + category + ", number=" + number + ")";
        };
    }

    public String getErrorCategory() {
        return errorCategory;
    }

    public String getErrorNumber() {
        return errorNumber;
    }
}