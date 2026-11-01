package fixture;

import java.util.Set;

/** Independent native settings fixture; configured identically to the legacy side per case. */
public final class BankSchemaValidationSettings {
    private static Set<String> channels = Set.of();
    private static Set<String> exclusions = Set.of();

    private BankSchemaValidationSettings() { }

    public static void configure(Set<String> validationChannels, Set<String> excludedApplications) {
        channels = Set.copyOf(validationChannels);
        exclusions = Set.copyOf(excludedApplications);
    }

    public static Set<String> channels() { return channels; }
    public static Set<String> exclusions() { return exclusions; }
}
