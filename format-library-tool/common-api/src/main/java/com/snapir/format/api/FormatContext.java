package com.snapir.format.api;

import java.util.Map;
import java.util.Objects;

/**
 * Explicit native runtime fields shared by formats and decorators. API version: 1.
 *
 * <p>The caller owns and supplies a mutable map. It may contain channel/application settings,
 * other business fields, and nested native values. The map is deliberately not copied: delegated
 * calls observe writes immediately, including writes performed before an exception.
 * Use containsKey to distinguish a missing field from a field whose value is null.
 * No Composer lookup, initialization, routing or conversion behavior is implemented here.
 *
 * @param values non-null, caller-owned mutable map; values may be null
 */
public record FormatContext(Map<String, Object> values) {
    /** Retain the supplied map without changing its contents or write visibility. */
    public FormatContext {
        Objects.requireNonNull(values, "values");
    }
}
