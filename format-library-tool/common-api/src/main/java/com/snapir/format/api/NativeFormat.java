package com.snapir.format.api;

/**
 * Shared contract for native formats, wrappers and decorators. API version: 1.
 *
 * <p>Implementations preserve their original settings, conditions, exceptions and side effects.
 * A decorator receives its wrapped NativeFormat through its constructor; a wrapper receives its
 * configured children through its constructor. This interface does not prescribe their call order.
 * Implementations depend only on native Java data, never Composer runtime objects.
 */
public interface NativeFormat {
    /**
     * Format a supplied native value into an XML element.
     *
     * @param value native scalar, map, list or application object; null is a supplied null value
     * @param context shared runtime fields; reads and writes follow the original behavior
     * @return the formatted element, or null when the original behavior omits the element
     * @throws Exception when the original behavior requires a failure; do not suppress it merely
     *                   to satisfy this contract
     */
    XmlElement format(Object value, FormatContext context) throws Exception;

    /**
     * Parse an XML element into its native value.
     *
     * <p>This operation need not reverse format. Preserve the actual source-defined transformation.
     * Additional context writes, including writes before a failure, remain visible to the caller.
     *
     * @param element input element, or null for an absent element
     * @param context shared runtime fields; reads and writes follow the original behavior
     * @return native scalar, map, list or application object; null is a valid result when defined
     *         by the original behavior, and is not by itself evidence of a context write
     * @throws Exception when the original behavior requires a failure
     */
    Object unformat(XmlElement element, FormatContext context) throws Exception;
}
