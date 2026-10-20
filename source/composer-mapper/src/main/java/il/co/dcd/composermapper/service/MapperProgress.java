package il.co.dcd.composermapper.service;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/** Records scoped Mapper events and periodically displays the current work item. */
public final class MapperProgress implements AutoCloseable {
    private static final DateTimeFormatter TIMESTAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ssXXX");
    private final BufferedWriter log;
    private final long started;
    private final ScheduledExecutorService heartbeat;
    private volatile String current = "Starting scoped generation";

    /** Opens a fresh run log and starts a daemon console heartbeat every five seconds. */
    public MapperProgress(Path path, long started) throws IOException {
        this.started = started;
        log = Files.newBufferedWriter(path, StandardCharsets.UTF_8);
        heartbeat = Executors.newSingleThreadScheduledExecutor(task -> {
            Thread thread = new Thread(task, "mapper-progress");
            thread.setDaemon(true);
            return thread;
        });
        heartbeat.scheduleAtFixedRate(() -> System.out.println(stamp("Progress: " + current
            + " | elapsed=" + elapsed(started))), 5, 5, TimeUnit.SECONDS);
    }

    /** Logs and flushes an event; major boundaries can also be displayed immediately. */
    public void event(String message, boolean display) {
        current = message;
        String line = stamp(message);
        try {
            log.write(line);
            log.newLine();
            log.flush();
        } catch (IOException e) {
            throw new UncheckedIOException("Failed writing Mapper progress log", e);
        }
        if (display) System.out.println(line);
    }

    /** Formats monotonic wall duration, including hours for long enterprise runs. */
    public static String elapsed(long started) {
        long seconds = TimeUnit.NANOSECONDS.toSeconds(System.nanoTime() - started);
        return String.format("%02d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60);
    }

    /** Returns a timestamped event using the executing computer's local offset. */
    public static String stamp(String message) { return "[" + OffsetDateTime.now().format(TIMESTAMP) + "] " + message; }

    /** Stops periodic output and closes the log on success or failure. */
    @Override public void close() throws IOException {
        heartbeat.shutdownNow();
        log.close();
    }
}
