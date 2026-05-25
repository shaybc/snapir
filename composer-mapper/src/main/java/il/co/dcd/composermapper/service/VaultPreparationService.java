package il.co.dcd.composermapper.service;

import java.io.IOException;
import java.nio.file.*;
import java.util.Comparator;

public class VaultPreparationService {

    public void prepare(Path vault, boolean clean) {
        try {
            if (clean) {
                delete(vault.resolve("operations"));
                delete(vault.resolve("opsteps"));
                delete(vault.resolve("formats"));
                delete(vault.resolve("contexts"));
                delete(vault.resolve("classes"));
                delete(vault.resolve("channels"));
                delete(vault.resolve("analysis"));
            }
            Files.createDirectories(vault.resolve("analysis"));
            Files.createDirectories(vault.resolve("channels"));
        } catch (IOException e) {
            throw new RuntimeException("Failed preparing vault", e);
        }
    }

    private void delete(Path p) throws IOException {
        if (!Files.exists(p)) return;
        try (var s = Files.walk(p)) {
            s.sorted(Comparator.reverseOrder()).forEach(x -> {
                try { Files.deleteIfExists(x); } catch (IOException e) { throw new RuntimeException(e); }
            });
        }
    }
}
