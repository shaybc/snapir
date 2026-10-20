package il.co.dcd.composermapper.util;

/** Selects operation steps using their declared onlyFor channel restriction. */
public final class ChannelStepSelection {
    private ChannelStepSelection() {}

    /**
     * Tests whether an unrestricted or comma-separated onlyFor value allows a channel.
     * @param onlyFor source restriction, or null for all channels
     * @param channel channel whose effective operation is being mapped
     * @return whether the step applies, without modifying its definition
     */
    public static boolean applies(String onlyFor, String channel) {
        if (onlyFor == null || onlyFor.isBlank()) return true;
        for (String allowed : onlyFor.split(",")) {
            if (allowed.trim().equalsIgnoreCase(channel)) return true;
        }
        return false;
    }
}
