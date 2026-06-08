package com.ibm.il.dse.operations.common;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

/**
 * Shared utility opStep. Sets ErrorCategory and ErrorNumber in context.
 * Used by virtually every operation for error handling.
 *
 * XML attributes (passed via setter methods):
 *   ErrorCategory - string category code (e.g. "10", "99")
 *   ErrorNumber   - string error number within category (e.g. "0", "4")
 *
 * Returns:
 *   0 - always (mapping always succeeds)
 */
public class MapErrorByValueAlways extends CCOperationStep {

    private String errorCategory = "99";
    private String errorNumber   = "0";

    public void setErrorCategory(String errorCategory) {
        this.errorCategory = errorCategory;
    }

    public void setErrorNumber(String errorNumber) {
        this.errorNumber = errorNumber;
    }

    @Override
    public int execute() throws Exception {
        Context ctx = getContext();
        ctx.setValueAt("ErrorCategory",   errorCategory);
        ctx.setValueAt("ErrorNumber",     errorNumber);
        ctx.setValueAt("ErrorDescription", resolveErrorDescription(errorCategory, errorNumber));
        return 0;
    }

    private String resolveErrorDescription(String category, String number) {
        // Lookup from error message catalog (simplified for demo)
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
