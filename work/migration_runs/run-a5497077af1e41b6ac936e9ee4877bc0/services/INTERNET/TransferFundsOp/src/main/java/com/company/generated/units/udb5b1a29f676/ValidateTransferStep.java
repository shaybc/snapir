package com.company.generated.units.udb5b1a29f676;

import java.util.Map;
import java.util.Objects;

/**
 * Validates that required context fields are present and non-blank:
 * SourceAccount, TargetAccount, Amount, Currency, SessionToken.
 *
 * Returns:
 *   0 - all required fields are present and non-blank
 *   1 - one or more required fields are missing or blank
 */
public class ValidateTransferStep {

    private static final String[] REQUIRED_FIELDS = {
        "SourceAccount",
        "TargetAccount",
        "Amount",
        "Currency",
        "SessionToken"
    };

    public int execute(Map<String, Object> context) {
        Objects.requireNonNull(context, "Context cannot be null");
        for (String field : REQUIRED_FIELDS) {
            Object value = context.get(field);
            if (value == null || String.valueOf(value).isBlank()) {
                context.put("ValidationFailedField", field);
                return 1;
            }
        }
        return 0;
    }
}
