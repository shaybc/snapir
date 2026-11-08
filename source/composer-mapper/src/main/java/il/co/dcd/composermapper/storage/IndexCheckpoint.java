package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.util.FileUtil;
import java.io.IOException;
import java.nio.file.*;
import java.security.MessageDigest;
import java.sql.*;
import java.util.*;

/** Immutable completed source index; rendered notes and partial output are never recovered. */
final class IndexCheckpoint {
    private static final String FILE = "analysis/index-checkpoint.sqlite";
    private IndexCheckpoint() {}

    static boolean exists(Path prior) { return prior != null && Files.exists(prior.resolve(FILE)); }

    /** Pins the mapper implementation, Java analyzer and runtime, not just a release label. */
    private static String policy() throws Exception {
        Path code = Path.of(IndexCheckpoint.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        var digest = MessageDigest.getInstance("SHA-256");
        digest.update(FileFactReuse.policy().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        if (Files.isRegularFile(code)) digest.update(FileUtil.rawSha256(code).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        else try (var paths = Files.walk(code)) {
            for (Path file : paths.filter(path -> path.toString().endsWith(".class")).sorted().toList()) {
                digest.update(code.relativize(file).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                digest.update(FileUtil.rawSha256(file).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static String configuration(Path root, String workspace, AnalysisSettings settings, String scope) throws IOException {
        return root.toRealPath() + "|" + workspace + "|" + new TreeMap<>(settings.metadata()) + "|" + scope;
    }

    /** Copies a verified checkpoint into a fresh destination; failed builders remain untouched. */
    static boolean restore(Path prior, Path target, Path root, String workspace, AnalysisSettings settings, String scope) {
        if (!exists(prior)) return false;
        Path checkpoint = prior.resolve(FILE);
        try {
            String expected = Files.readString(prior.resolve(FILE + ".sha256")).strip();
            if (!expected.equals(FileUtil.rawSha256(checkpoint))) throw new IOException("Checkpoint digest differs");
            Class.forName("org.sqlite.JDBC");
            try (var connection = DriverManager.getConnection("jdbc:sqlite:" + checkpoint.toAbsolutePath().toUri() + "?mode=ro&immutable=1")) {
                try (var statement = connection.createStatement(); var result = statement.executeQuery("PRAGMA integrity_check")) {
                    if (!result.next() || !"ok".equals(result.getString(1))) throw new IOException("Checkpoint integrity check failed");
                }
                if (!"true".equals(revision(connection, "index_stage_complete"))
                    || !policy().equals(revision(connection, "index_stage_policy"))
                    || !configuration(root, workspace, settings, scope).equals(revision(connection, "index_stage_configuration")))
                    throw new IOException("Checkpoint mapper version or configuration differs");
                verifySources(connection, root);
            }
            Files.createDirectories(target.getParent());
            Files.copy(checkpoint, target);
            if (!expected.equals(FileUtil.rawSha256(target))) throw new IOException("Checkpoint changed during copy");
            return true;
        } catch (Exception error) {
            try { Files.deleteIfExists(target); } catch (IOException cleanup) { error.addSuppressed(cleanup); }
            System.out.println("Completed source index not reusable; rebuilding source index: " + error.getMessage());
            System.out.flush();
            return false;
        }
    }

    private static String revision(Connection connection, String key) throws SQLException {
        try (var statement = connection.prepareStatement("SELECT value FROM revision WHERE key=?")) {
            statement.setString(1, key);
            try (var result = statement.executeQuery()) { return result.next() ? result.getString(1) : null; }
        }
    }

    /** Publishes the index snapshot only after catalog construction and source verification finish. */
    static void save(AnalysisSession session, String scope) throws Exception {
        verifySources(session.store.connection, session.root);
        var store = session.store;
        store.execute("INSERT OR REPLACE INTO revision VALUES ('index_stage_complete','true')");
        store.execute("INSERT OR REPLACE INTO revision VALUES ('index_stage_policy',?)", policy());
        store.execute("INSERT OR REPLACE INTO revision VALUES ('index_stage_configuration',?)",
            configuration(session.root, session.workspace, session.settings, scope));
        store.commit();
        Path target = session.vault.resolve(FILE), temporary = session.vault.resolve(FILE + ".tmp");
        Files.deleteIfExists(temporary);
        try (var connection = DriverManager.getConnection("jdbc:sqlite:" + session.database.toAbsolutePath().toUri() + "?mode=ro")) {
            try (var statement = connection.prepareStatement("VACUUM main INTO ?")) {
                statement.setString(1, temporary.toString()); statement.execute();
            }
        }
        String hash = FileUtil.rawSha256(temporary);
        Files.move(temporary, target, StandardCopyOption.ATOMIC_MOVE);
        Path hashTemporary = session.vault.resolve(FILE + ".sha256.tmp");
        Files.writeString(hashTemporary, hash + "\n");
        Files.move(hashTemporary, session.vault.resolve(FILE + ".sha256"), StandardCopyOption.ATOMIC_MOVE);
    }

    /** Checks source bytes and membership with streaming queries and bounded memory. */
    static void verifySources(Connection connection, Path root) {
        try {
            Path realRoot = root.toRealPath();
            int expected = 0;
            try (var statement = connection.createStatement(); var rows = statement.executeQuery("SELECT path,hash,complete FROM files")) {
                while (rows.next()) {
                    Path file = Path.of(rows.getString(1));
                    if (rows.getInt(3) != 1 || !file.toRealPath().startsWith(realRoot)
                        || !FileUtil.rawSha256(file).equals(rows.getString(2)))
                        throw new IllegalStateException("Source changed or incomplete: " + file);
                    expected++;
                }
            }
            try (var lookup = connection.prepareStatement("SELECT path FROM files WHERE path=?"); var paths = Files.walk(root)) {
                var iterator = paths.filter(Files::isRegularFile).iterator(); int count = 0;
                while (iterator.hasNext()) {
                    Path file = iterator.next().toAbsolutePath().normalize();
                    if (!AnalysisSession.sourceFile(file)) continue;
                    lookup.setString(1, file.toString());
                    try (var row = lookup.executeQuery()) {
                        if (!row.next()) throw new IllegalStateException("Source added during mapping: " + file);
                    }
                    count++;
                }
                if (count != expected) throw new IllegalStateException("Source membership changed during mapping");
            }
        } catch (IOException | SQLException error) { throw new IllegalStateException("Could not verify map source revision", error); }
    }
}
