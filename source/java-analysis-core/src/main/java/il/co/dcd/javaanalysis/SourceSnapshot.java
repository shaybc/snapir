package il.co.dcd.javaanalysis;

import java.io.IOException;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.*;
import java.util.HexFormat;

/** One bounded source revision; decoding fallbacks reuse captured bytes, never reopen it. */
public record SourceSnapshot(Path path, String hash, String encoding, String text) {
    public static final long MAX_BYTES = 8L * 1024 * 1024;

    /** Capture and hash raw bytes, preserving the existing Hebrew fallback and BOM policy. */
    public static SourceSnapshot read(Path path, boolean stripBom) throws IOException {
        if (Files.size(path) > MAX_BYTES) throw new IOException("Java source exceeds analysis byte limit: " + path);
        byte[] bytes;
        try (var stream = Files.newInputStream(path)) {
            bytes = stream.readNBytes((int) MAX_BYTES + 1);
        }
        if (bytes.length > MAX_BYTES) throw new IOException("Java source grew beyond analysis byte limit: " + path);
        String text, encoding = "UTF-8";
        try { text = StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException error) {
            encoding = "windows-1255";
            text = Charset.forName(encoding).newDecoder().decode(java.nio.ByteBuffer.wrap(bytes)).toString();
            System.err.println("[Java encoding] UTF-8 decoding failed; using Windows-1255: " + path);
        }
        if (stripBom && text.startsWith("\ufeff")) text = text.substring(1);
        try {
            return new SourceSnapshot(path.toAbsolutePath().normalize(),
                HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)), encoding, text);
        } catch (NoSuchAlgorithmException error) { throw new IllegalStateException(error); }
    }
}
