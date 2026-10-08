package com.company.generated.support.format;

/** Transform serialized field values without accessing the operation context. */
public interface ValueDecorator {
    String addDecoration(String value);
    String removeDecoration(String value);
}
