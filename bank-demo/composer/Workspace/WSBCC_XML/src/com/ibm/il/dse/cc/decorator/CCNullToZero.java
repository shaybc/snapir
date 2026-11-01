package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.FormatDecoratorHolder;

/** Demo policy: convert null or empty to zero in both directions, without trimming. */
public class CCNullToZero extends FormatDecoratorHolder {
    @Override
    public String addDecoration(String value) { return zeroIfEmpty(value); }

    @Override
    public String removeDecoration(String value) { return zeroIfEmpty(value); }

    private String zeroIfEmpty(String value) {
        return value == null || value.isEmpty() ? "0" : value;
    }
}
