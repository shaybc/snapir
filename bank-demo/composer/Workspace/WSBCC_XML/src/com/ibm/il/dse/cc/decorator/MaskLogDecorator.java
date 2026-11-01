package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.FormatDecoratorHolder;

/**
 * Masks sensitive values in log output. Applied to fields like SessionToken, Pin.
 *
 * Format direction (addDecoration):    no-op in this demo
 * Unformat direction (removeDecoration): no-op (value passes through unchanged)
 *
 * This fixture does not implement a log subsystem or emit masked log records.
 */
public class MaskLogDecorator extends FormatDecoratorHolder {

    @Override
    public String addDecoration(String value) {
        // The demo emits no log record; the XML value is returned unchanged.
        return value;
    }

    @Override
    public String removeDecoration(String value) {
        return value;
    }
}
