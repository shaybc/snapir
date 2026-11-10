package il.co.dcd.verification;

/** Diagnose slow traversal operations without logging source expressions or configuration. */
final class NodeProcessingProgress implements AutoCloseable {
    private record State(String description, long started, Thread thread) { }
    private static volatile State current;
    private final State previous;
    static {
        Thread watcher = new Thread(() -> {
            long lastReport = 0;
            while (true) {
                try { Thread.sleep(1000); }
                catch (InterruptedException stopped) { return; }
                State state = current;
                if (state == null || System.nanoTime() - state.started() < 5_000_000_000L) continue;
                if (System.nanoTime() - lastReport < 5_000_000_000L) continue;
                lastReport = System.nanoTime();
                StringBuilder detail = new StringBuilder(state.description());
                detail.append("; operation elapsed=").append((System.nanoTime() - state.started()) / 1_000_000_000L).append("s; stack=");
                StackTraceElement[] stack = state.thread().getStackTrace();
                for (int i = 0; i < Math.min(stack.length, 12); i++) detail.append(stack[i]).append(" <- ");
                AnalysisProgress.report("slow operation " + detail);
            }
        }, "boundary-node-watchdog");
        watcher.setDaemon(true);
        watcher.start();
    }
    private NodeProcessingProgress(String description) {
        previous = current;
        current = new State((previous == null ? "" : previous.description() + " > ") + description,
                            System.nanoTime(), Thread.currentThread());
    }
    static NodeProcessingProgress operation(String description) { return new NodeProcessingProgress(description); }
    public void close() { current = previous; }
}
