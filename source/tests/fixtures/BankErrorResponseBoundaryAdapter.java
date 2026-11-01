package fixture;

import il.co.dcd.verification.harness.BoundaryAdapter;
import java.util.Map;
import org.w3c.dom.Element;

/** Independent native test fixture for StandardErrorRSFmt, never live AI acceptance evidence. */
public class BankErrorResponseBoundaryAdapter implements BoundaryAdapter {
    public Object invoke(String xml, Map<String, Object> context, Element configuration) {
        String description = (String) context.get("ErrorDescription");
        String channel = (String) context.get("CHANNEL_NAME");
        String application = (String) context.get("APPLICATION");
        boolean channelEnabled = BankSchemaValidationSettings.channels().contains(channel.toLowerCase());
        boolean applicationAllowed = !BankSchemaValidationSettings.exclusions().contains(application.toLowerCase());
        boolean empty = description == null || description.length() == 0;
        boolean nil = channelEnabled && applicationAllowed && empty;
        return "<ErrorReply>"
            + element("ErrorCategory", (String) context.get("ErrorCategory"), false)
            + element("ErrorNumber", (String) context.get("ErrorNumber"), false)
            + element("ErrorDescription", description, nil)
            + element("RequestId", (String) context.get("RequestId"), false)
            + "</ErrorReply>";
    }

    private static String element(String name, String value, boolean nil) {
        String attributes = nil ? " xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:nil=\"true\"" : "";
        if (value == null) return "<" + name + attributes + "/>";
        return "<" + name + attributes + ">" + escape(value) + "</" + name + ">";
    }

    private static String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
