package com.company.generated.units.u3edad4d894ed;

import java.util.Map;
import java.util.Objects;

/**
 * Configured step: SkipFraudOnTimeout
 * ImplClass: com.ibm.il.dse.operations.common.SetChannelContext
 * XML attributes: FieldName = "FraudCheckSkipped", FieldValue = "true"
 * Routing: on0Do = "ExecuteTransfer", onOtherDo = "TechnicalError"
 */
public class SkipFraudOnTimeoutStep {

    private final String fieldName;
    private final String fieldValue;

    public SkipFraudOnTimeoutStep() {
        this.fieldName = "FraudCheckSkipped";
        this.fieldValue = "true";
    }

    public SkipFraudOnTimeoutStep(String fieldName, String fieldValue) {
        this.fieldName = fieldName;
        this.fieldValue = fieldValue;
    }

    public String getFieldName() {
        return fieldName;
    }

    public String getFieldValue() {
        return fieldValue;
    }

    public int execute(Map<String, Object> context) {
        Map<String, Object> ctx = Objects.requireNonNull(context, "Operation context map");
        if (fieldName != null) {
            ctx.put(fieldName, fieldValue);
        }
        return 0;
    }
}
