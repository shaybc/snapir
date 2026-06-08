package com.ibm.il.dse.operations.common;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

/**
 * Shared utility opStep. Validates that required context fields are present and non-blank.
 *
 * XML attributes:
 *   RequiredFields - comma-separated list of field names that must be present in context
 *
 * Returns:
 *   0 - all required fields are present and non-blank
 *   1 - one or more required fields are missing or blank
 */
public class ValidateInputFields extends CCOperationStep {

    private String requiredFields = "";

    public void setRequiredFields(String requiredFields) {
        this.requiredFields = requiredFields;
    }

    @Override
    public int execute() throws Exception {
        Context ctx = getContext();
        if (requiredFields == null || requiredFields.isBlank()) return 0;

        for (String field : requiredFields.split(",")) {
            String name  = field.trim();
            Object value = ctx.getValueAt(name);
            if (value == null || String.valueOf(value).isBlank()) {
                ctx.setValueAt("ValidationFailedField", name);
                return 1;
            }
        }
        return 0;
    }
}
