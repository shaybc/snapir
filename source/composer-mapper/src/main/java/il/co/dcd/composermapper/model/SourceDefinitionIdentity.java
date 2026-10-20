package il.co.dcd.composermapper.model;

import il.co.dcd.composermapper.util.FileUtil;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.w3c.dom.Element;

/** An original definition occurrence, independent of note copies and content revisions. */
public record SourceDefinitionIdentity(String kind, String name, String channel,
        Path file, String relativePath, String selector, String owner, Element element) {
    public String key(String workspace) {
        return digest(workspace, kind, relativePath, selector);
    }

    /** Length-delimited fields avoid ambiguous keys when source names contain separators. */
    public static String digest(String... fields) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String field : fields) {
                byte[] bytes = String.valueOf(field).getBytes(StandardCharsets.UTF_8);
                digest.update((bytes.length + ":").getBytes(StandardCharsets.UTF_8));
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public String revision() { return FileUtil.sha256(file); }
}
