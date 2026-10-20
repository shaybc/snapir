package il.co.dcd.composermapper.util;

import java.io.IOException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** Reads Java sources from workspaces containing UTF-8 and Windows-1255 files. */
public final class JavaSourceReader {
    private static final Charset HEBREW_WINDOWS = Charset.forName("windows-1255");

    private JavaSourceReader() {}

    /**
     * Reads without changing the source, logging a Windows-1255 fallback to stderr.
     * @param sourceFile Java source to read
     * @return decoded source text
     * @throws IOException if reading fails or neither encoding can decode the file
     */
    public static String read(Path sourceFile) throws IOException {
        try {
            return Files.readString(sourceFile, StandardCharsets.UTF_8);
        } catch (CharacterCodingException e) {
            String content = Files.readString(sourceFile, HEBREW_WINDOWS);
            System.err.println("[Java encoding] UTF-8 decoding failed; using Windows-1255: " + sourceFile);
            return content;
        }
    }
}
