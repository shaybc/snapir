package com.ibm.il.dse.cc.cut;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.DSEServerOperation;
import com.ibm.dse.base.KeyedCollection;
import com.ibm.dse.base.Tag;

import java.util.Hashtable;

/**
 * Base class for all WSBCC operations.
 * Loaded from XML via initializeFrom(Tag). Channel handler calls:
 *   1. unformat(requestXml)
 *   2. execute()
 *   3. format() -> returns response XML
 *
 * DO NOT instantiate directly. Defined as 'compound' in dse.ini operations section.
 */
public class CCDSEServerOperation extends DSEServerOperation {

    private static final int RC_TIMEOUT = -99;

    private String  operationName;
    private String  hostKey;
    private String  operationFields;
    private boolean writeToLog       = false;
    private boolean writeToOfecStat  = false;
    private boolean isSelectiveJournalising = false;

    private boolean returnedErrorBodyChanged = false;
    private String  returnedErrorBodyChanger = null;

    private Hashtable formats  = new Hashtable();

    /**
     * Main execution loop. Called by channel handler after unformat().
     * Runs the opStep chain according to RC routing attributes.
     */
    @Override
    public void execute() throws Exception {
        // Pre-populate context with operationFields (key=value pairs)
        if (operationFields != null && !operationFields.isBlank()) {
            setFields(operationFields);
        }

        // Remove opSteps that are not applicable to this channel (onlyFor filtering)
        removeOpStepsNotForThisChannel();
        if (operationSteps().isEmpty()) return;

        // Run the opStep chain
        int index = 0;
        do {
            KeyedCollection kc = getOperationStep(index);
            index = processOpStep(kc, operationName, index);
        } while (index != -1);

        // Substitute error reply format if on{N}Return was triggered
        if (isReturnedErrorBodyChanged() && getReturnedErrorBodyChanger() != null) {
            // The channel handler reads csErrorReplyFormat instead of csReplyFormat
            substituteErrorReplyFormat();
        }
    }

    /**
     * Routes from one opStep to the next based on the return code.
     * Priority order:
     *   1. on{N}Return  -- switch error reply format body before routing
     *   2. onTimeoutDo  -- if RC == RC_TIMEOUT
     *   3. on{N}Do      -- exact RC match
     *   4. onOtherDo    -- default when no on{N}Do matches
     *   5. onOtherDoDefault -- final fallback (logs warning)
     */
    private int processOpStep(KeyedCollection kc, String opName, int currentIndex) throws Exception {
        kc.getImplementation().setContext(getContext());
        int code = kc.getImplementation().execute();
        String reply = kc.getAttribute("on" + code + "Return");
        if (reply != null) {
            returnedErrorBodyChanged = true;
            returnedErrorBodyChanger = reply;
        }
        String target = code == RC_TIMEOUT ? kc.getAttribute("onTimeoutDo") : null;
        if (target == null) target = kc.getAttribute("on" + code + "Do");
        if (target == null) target = kc.getAttribute("onOtherDo");
        if (target == null) {
            target = kc.getAttribute("onOtherDoDefault");
            java.util.logging.Logger.getLogger(getClass().getName()).warning("Using default route for " + opName);
        }
        if (target == null || "end".equals(target)) return -1;
        if ("next".equals(target)) return currentIndex + 1 < operationSteps().size() ? currentIndex + 1 : -1;
        for (int offset = 0; offset < operationSteps().size(); offset++) {
            int candidate = (currentIndex + offset) % operationSteps().size();
            if (target.equals(getOperationStep(candidate).getAttribute("id"))) return candidate;
        }
        throw new IllegalStateException("Unknown demo step target: " + target);
    }

    private void removeOpStepsNotForThisChannel() {
        String channel = String.valueOf(getContext().getValueAt("CHANNEL_NAME"));
        operationSteps().removeIf(step -> {
            String onlyFor = step.getAttribute("onlyFor");
            return onlyFor != null && !java.util.Arrays.stream(onlyFor.split("[,;\\s]+")).anyMatch(channel::equalsIgnoreCase);
        });
    }

    private void setFields(String operationFields) {
        for (String field : operationFields.split(",")) {
            String[] pair = field.split("=", 2);
            if (pair.length != 2) throw new IllegalArgumentException("Invalid demo operation field: " + field);
            getContext().setValueAt(pair[0].trim(), pair[1].trim());
        }
    }

    private void substituteErrorReplyFormat() {
        if (!formats.containsKey(returnedErrorBodyChanger)) {
            throw new IllegalStateException("Unknown error reply format: " + returnedErrorBodyChanger);
        }
        formats.put("csErrorReplyFormat", formats.get(returnedErrorBodyChanger));
    }

    public boolean isReturnedErrorBodyChanged()  { return returnedErrorBodyChanged; }
    public String  getReturnedErrorBodyChanger() { return returnedErrorBodyChanger; }
    public Hashtable getFormats()                { return formats; }
    public String getHostKey()                   { return hostKey; }
    public void setHostKey(String v)             { this.hostKey = v; }
    public String getOperationFields()           { return operationFields; }
    public void setOperationFields(String v)     { this.operationFields = v; }
    public boolean isWriteToLog()                { return writeToLog; }
    public void setWriteToLog(boolean v)         { this.writeToLog = v; }
}
