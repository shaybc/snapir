package com.company.generated.units.u9d214a54d7b1;

import java.util.Map;
import java.util.Objects;

/**
 * Native implementation of the configured TechnicalError step (MapErrorByValueAlways).
 * Sets ErrorCategory, ErrorNumber, and ErrorDescription in the context map.
 * XML Configuration: ErrorCategory="99", ErrorNumber="0"
 */
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

    public String getErrorCategory() {
        return errorCategory;
    }

    public String getErrorNumber() {
        return errorNumber;
    }

    public int execute(Map<String, Object> context) {
        Objects.requireNonNull(context, "Context map must not be null");
        context.put("ErrorCategory", errorCategory);
        context.put("ErrorNumber", errorNumber);
        context.put("ErrorDescription", resolveErrorDescription(errorCategory, errorNumber));
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
}
