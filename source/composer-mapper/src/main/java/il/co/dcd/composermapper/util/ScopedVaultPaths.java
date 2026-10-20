package il.co.dcd.composermapper.util;

/** Scope original entity names through channel, operation, and resource-origin folders. */
public final class ScopedVaultPaths {
    private ScopedVaultPaths() {}

    public static String segment(String name) {
        return SafePathNames.segment(name, false);
    }

    /** Groups step filenames as Windows does, without changing the source label or routing. */
    public static String stepGroupKey(String name) {
        return segment(name).toLowerCase(java.util.Locale.ROOT);
    }

    public static String operation(String channel, String operation) {
        return "channels/" + segment(channel) + "/operations/" + segment(operation);
    }

    public static String classPath(String fqcn) {
        return String.join("/", java.util.Arrays.stream(fqcn.split("\\.")).map(ScopedVaultPaths::segment).toList());
    }

    public static String inventory(String prefix, String folder, String sourcePath, String selector, String name) {
        if (folder.equals("classes")) return prefix + "/classes/" + sourcePath.replaceFirst("(?i)\\.java$", ".md");
        String[] parts = sourcePath.split("/");
        int start = parts.length - 1;
        for (int i = 0; i < parts.length - 2; i++) {
            if (parts[i].equalsIgnoreCase("Channel")) start = i + 2;
        }
        java.util.List<String> origin = new java.util.ArrayList<>();
        for (int i = start; i < parts.length - 1; i++) origin.add(segment(parts[i]));
        if (origin.isEmpty() || !origin.getLast().equalsIgnoreCase("defaultFile"))
            origin.add(segment(parts[parts.length - 1].replaceFirst("(?i)\\.xml$", "")));
        return prefix + "/" + folder + "/" + String.join("/", origin) + "/" + segment(name) + ".md";
    }
}
