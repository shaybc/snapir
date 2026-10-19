package com.company.generated.units.u3643d2141e0a;

import com.company.generated.units.u3a42c4326e3d.OperationContext;
import java.util.Objects;

/**
 * Configured unit NoLinksFound corresponding to MapErrorByValueAlways
 * with ErrorCategory="20" and ErrorNumber="1".
 */
public class NoLinksFoundStep {
    private final String errorCategory;
    private final String errorNumber;

    public NoLinksFoundStep() {
        this.errorCategory = "20";
        this.errorNumber = "1";
    }

    public NoLinksFoundStep(String errorCategory, String errorNumber) {
        this.errorCategory = Objects.requireNonNull(errorCategory, "errorCategory");
        this.errorNumber = Objects.requireNonNull(errorNumber, "errorNumber");
    }

    public String getErrorCategory() {
        return errorCategory;
    }

    public String getErrorNumber() {
        return errorNumber;
    }

    public int execute(OperationContext context) {
        OperationContext ctx = Objects.requireNonNull(context, "OperationContext");
        ctx.setValueAt("ErrorCategory", errorCategory);
        ctx.setValueAt("ErrorNumber", errorNumber);
        ctx.setValueAt("ErrorDescription", resolveErrorDescription(errorCategory, errorNumber));
        return 0;
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
