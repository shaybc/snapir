package com.company.generated.units.u3a42c4326e3d;

import java.util.HashMap;
import java.util.Map;

/**
 * Native Java business step equivalent to MapErrorByValueAlways with ErrorCategory="99" and ErrorNumber="8".
 */
public class DatabaseErrorStep {

    private final String errorCategory = "99";
    private final String errorNumber = "8";

    public int execute(Map<String, Object> context) {
        if (context == null) {
            throw new IllegalArgumentException("Context map cannot be null");
        }
        context.put("ErrorCategory", errorCategory);
        context.put("ErrorNumber", errorNumber);
        context.put("ErrorDescription", resolveErrorDescription(errorCategory, errorNumber));
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
