package com.company.generated.decorator;

/**
 * Sets xsi:nil="true" attribute when value is null or empty.
 * Implements Type 1 decorator contract.
 *
 * Format direction (addDecoration):   null/empty -> add xsi:nil="true" attribute
 * Unformat direction (removeDecoration): xsi:nil value -> return null
 */
public class NilDecorator {

    /** Called during FORMAT. If value is null/empty, adds nil attribute. */
    public String addDecoration(String value) {
        if (value == null || value.isBlank()) {
            // Signal to parent formatter to emit xsi:nil="true"
            return null;
        }
        return value;
    }

    /** Called during UNFORMAT (in reverse chain order). Null value -> empty string. */
    public String removeDecoration(String value) {
        if (value == null) return "";
        return value;
    }
}