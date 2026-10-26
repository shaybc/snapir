package com.ibm.dse.base;

import java.util.Map;
import java.util.logging.Logger;

/** Demo attribute decorator boundary; the formatter supplies its formatted field value. */
public abstract class AttributeXmlFormatDecoratorImpl {
    protected final Logger logger = Logger.getLogger(getClass().getName());

    /** Additional attributes belong to the decorated field, not the parent XML element. */
    public abstract Map<String, String> formatXmlAttributes(Context context, String formattedValue);
}
