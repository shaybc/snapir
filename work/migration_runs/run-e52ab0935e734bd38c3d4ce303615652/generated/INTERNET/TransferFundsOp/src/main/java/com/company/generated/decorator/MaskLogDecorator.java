package com.company.generated.decorator;

/**
 * Masks sensitive values in log output. Applied to fields like SessionToken, Pin.
 *
 * Format direction (addDecoration):    replaces all characters with '*' in logs
 * Unformat direction (removeDecoration): no-op (value passes through unchanged)
 *
 * Note: masking only applies to the log subsystem, not to the actual XML output.
 */
public class MaskLogDecorator {

    public String addDecoration(String value) {
        // Actual masking is applied by the log framework when it sees this decorator
        // The XML value is returned unchanged
        return value;
    }

    public String removeDecoration(String value) {
        return value;
    }
}