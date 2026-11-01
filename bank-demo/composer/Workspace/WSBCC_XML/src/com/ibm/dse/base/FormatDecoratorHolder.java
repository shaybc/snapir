package com.ibm.dse.base;

/** Executable demo value-decorator contract; defaults preserve the supplied value. */
public class FormatDecoratorHolder {
    public Object initializeFrom(Tag tag) { return this; }
    public String addDecoration(String value) { return value; }
    public String removeDecoration(String value) { return value; }
}
