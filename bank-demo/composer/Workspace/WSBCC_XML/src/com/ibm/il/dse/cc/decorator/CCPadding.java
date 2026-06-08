package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.FormatDecoratorHolder;
import com.ibm.dse.base.Tag;

/**
 * Pads a string to a fixed length using a specified pad character.
 *
 * Attributes:
 *   padChar  - character to use for padding (default '0')
 *   length   - target length after padding
 *   padLeft  - "true" to pad on left (default), "false" to pad on right
 *
 * Format direction (addDecoration):    pad value to target length
 * Unformat direction (removeDecoration): strip the padding characters
 *
 * Decorator chain example with two decorators:
 *   <CCString dataName="AccountNumber"/>
 *   <RemoveLeadingZerosDecorator/>
 *   <CCPadding padChar="0" length="10"/>
 *
 *   format:   "12345" -> RemoveLeadingZeros.add (no-op) -> CCPadding.add -> "0000012345"
 *   unformat: "0000012345" -> CCPadding.remove -> "12345" -> RemoveLeadingZeros.remove -> "12345"
 */
public class CCPadding extends FormatDecoratorHolder {

    private char    padChar = '0';
    private int     length  = 0;
    private boolean padLeft = true;

    @Override
    public Object initializeFrom(Tag tag) {
        String pc = tag.getAttribute("padChar");
        if (pc != null && !pc.isBlank()) this.padChar = pc.charAt(0);
        String len = tag.getAttribute("length");
        if (len != null) this.length = Integer.parseInt(len.trim());
        String pl = tag.getAttribute("padLeft");
        if ("false".equalsIgnoreCase(pl)) this.padLeft = false;
        return this;
    }

    @Override
    public String addDecoration(String value) {
        if (value == null) value = "";
        if (value.length() >= length) return value;
        String pad = String.valueOf(padChar).repeat(length - value.length());
        return padLeft ? pad + value : value + pad;
    }

    @Override
    public String removeDecoration(String value) {
        if (value == null) return null;
        if (padLeft) {
            return value.replaceFirst("^[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+", "");
        } else {
            return value.replaceFirst("[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+$", "");
        }
    }
}
