package com.company.generated;

import com.company.generated.Tag;

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
 */
public class CCPadding {

    private char    padChar = '0';
    private int     length  = 0;
    private boolean padLeft = true;

    public Object initializeFrom(Tag tag) {
        String pc = tag.getAttribute("padChar");
        if (pc != null && !pc.isBlank()) this.padChar = pc.charAt(0);
        String len = tag.getAttribute("length");
        if (len != null) this.length = Integer.parseInt(len.trim());
        String pl = tag.getAttribute("padLeft");
        if ("false".equalsIgnoreCase(pl)) this.padLeft = false;
        return this;
    }

    public String addDecoration(String value) {
        if (value == null) value = "";
        if (value.length() >= length) return value;
        String pad = String.valueOf(padChar).repeat(length - value.length());
        return padLeft ? pad + value : value + pad;
    }

    public String removeDecoration(String value) {
        if (value == null) return null;
        if (padLeft) {
            return value.replaceFirst("^[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+", "");
        } else {
            return value.replaceFirst("[" + java.util.regex.Pattern.quote(String.valueOf(padChar)) + "]+$", "");
        }
    }
}