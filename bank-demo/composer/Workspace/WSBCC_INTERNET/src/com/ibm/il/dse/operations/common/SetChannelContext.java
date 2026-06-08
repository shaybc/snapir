package com.ibm.il.dse.operations.common;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

/**
 * Shared utility opStep. Sets a named context field to a fixed value.
 * Useful for marking flags or states during operation execution.
 *
 * XML attributes:
 *   FieldName  - name of context field to set
 *   FieldValue - value to assign (string)
 *
 * Returns: 0 always
 */
public class SetChannelContext extends CCOperationStep {

    private String fieldName  = null;
    private String fieldValue = null;

    public void setFieldName(String fieldName)   { this.fieldName  = fieldName;  }
    public void setFieldValue(String fieldValue) { this.fieldValue = fieldValue; }

    @Override
    public int execute() throws Exception {
        if (fieldName != null) {
            getContext().setValueAt(fieldName, fieldValue);
        }
        return 0;
    }
}
