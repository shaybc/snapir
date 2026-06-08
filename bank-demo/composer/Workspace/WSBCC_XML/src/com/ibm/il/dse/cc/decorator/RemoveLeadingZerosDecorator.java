package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.FormatDecoratorHolder;

/**
 * Strips leading zeros from a numeric string.
 *
 * Format direction (addDecoration):    no-op (value passes through unchanged)
 * Unformat direction (removeDecoration): strips leading zeros from value
 *
 * Example:
 *   removeDecoration("000123") -> "123"
 *   removeDecoration("0")      -> "0"  (preserve single zero)
 */
public class RemoveLeadingZerosDecorator extends FormatDecoratorHolder {

    @Override
    public String addDecoration(String value) {
        // No-op in format direction
        return value;
    }

    @Override
    public String removeDecoration(String value) {
        if (value == null || value.isBlank()) return value;
        String stripped = value.replaceFirst("^0+(?!$)", "");
        return stripped.isEmpty() ? "0" : stripped;
    }
}
