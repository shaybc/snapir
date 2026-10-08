package il.co.dcd.composermapper.index;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class JavaClassIndexer {
    private static final Pattern PACKAGE_PATTERN = Pattern.compile("(?m)^\\s*package\\s+([a-zA-Z0-9_.]+)\\s*;");
    private static final Pattern CLASS_PATTERN = Pattern.compile("(?m)^\\s*(?:public\\s+)?(?:abstract\\s+|final\\s+)?(?:class|interface|enum)\\s+([A-Za-z_][A-Za-z0-9_]*)\\b");

    public void index(Path javaFile, Indexes indexes) {
        try {
            String content = Files.readString(javaFile, StandardCharsets.UTF_8);
            String pkg = matchFirst(PACKAGE_PATTERN, content);
            String cls = matchFirst(CLASS_PATTERN, content);
            if (cls == null || cls.isBlank()) {
                return;
            }
            String fqcn = (pkg == null || pkg.isBlank()) ? cls : pkg + "." + cls;
            indexes.classToSource().put(fqcn, javaFile);
        } catch (IOException e) {
            throw new RuntimeException("Failed indexing Java: " + javaFile, e);
        }
    }

    private String matchFirst(Pattern pattern, String text) {
        Matcher matcher = pattern.matcher(text);
        return matcher.find() ? matcher.group(1) : null;
    }
}
