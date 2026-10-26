package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.AttributeXmlFormatDecoratorImpl;
import com.ibm.dse.base.Context;
import com.ibm.dse.base.SchemaValidationSettings;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Level;

/** Demo attribute decorator preserving the supplied Composer runtime conditions.
 * The enclosing formatter calls this with the decorated field's formatted value.
 * This has no value transformation or unformat override.
 */
public class NilDecorator extends AttributeXmlFormatDecoratorImpl {
    @Override
    public Map<String, String> formatXmlAttributes(Context context, String formattedValue) {
        Map<String, String> attributes = new HashMap<>();
        try {
            String channel = (String) context.getValueAt("CHANNEL_NAME");
            String application = (String) context.getValueAt("APPLICATION");
            if (SchemaValidationSettings.getChannelsToSchemaValidation().contains(channel.toLowerCase())
                    && !SchemaValidationSettings.getApplicationsToExcludeSchemaValidation().contains(application.toLowerCase())) {
                if (formattedValue == null || formattedValue.length() == 0) {
                    attributes.put("xsi:nil", "true");
                }
            }
        } catch (Exception exception) {
            logger.log(Level.WARNING, "NilDecorator error", exception);
        }
        return attributes;
    }
}
