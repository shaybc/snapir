package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.FormatDecoratorHolder;

/**
 * Sets xsi:nil="true" attribute when value is null or empty.
 * Implements Type 1 decorator contract (FormatDecoratorHolder).
 *
 * Format direction (addDecoration):   null/empty -> add xsi:nil="true" attribute
 * Unformat direction (removeDecoration): xsi:nil value -> return null
 */
public class NilDecorator extends FormatDecoratorHolder {

    /** Called during FORMAT. If value is null/empty, adds nil attribute. */
    @Override
    public String addDecoration(String value) {
        if (value == null || value.isBlank()) {
            // Signal to parent formatter to emit xsi:nil="true"
            return null;
        }
        return value;
    }

    /** Called during UNFORMAT (in reverse chain order). Null value -> empty string. */
    @Override
    public String removeDecoration(String value) {
        if (value == null) return "";
        return value;
    }
}
