package com.company.generated;

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
public class SetChannelContext {

    private String fieldName  = null;
    private String fieldValue = null;
    private Context context;

    public void setFieldName(String fieldName)   { this.fieldName  = fieldName;  }
    public void setFieldValue(String fieldValue) { this.fieldValue = fieldValue; }

    public void setContext(Context context) {
        this.context = context;
    }

    public Context getContext() {
        return this.context;
    }

    public int execute() throws Exception {
        if (fieldName != null) {
            getContext().setFieldValue(fieldName, fieldValue);
        }
        return 0;
    }
}