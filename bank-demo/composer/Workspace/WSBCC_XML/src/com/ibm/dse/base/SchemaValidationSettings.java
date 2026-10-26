package com.ibm.dse.base;

import java.util.Set;

/** Runtime configuration dependency for the demo's schema-validation policy. */
public final class SchemaValidationSettings {
    private static Set<String> channels = Set.of();
    private static Set<String> excludedApplications = Set.of();

    private SchemaValidationSettings() {}

    /** Configure normalized names; absent configuration enables no channels. */
    public static void configure(Set<String> validationChannels, Set<String> exclusions) {
        channels = Set.copyOf(validationChannels);
        excludedApplications = Set.copyOf(exclusions);
    }

    public static Set<String> getChannelsToSchemaValidation() {
        return channels;
    }

    public static Set<String> getApplicationsToExcludeSchemaValidation() {
        return excludedApplications;
    }
}
