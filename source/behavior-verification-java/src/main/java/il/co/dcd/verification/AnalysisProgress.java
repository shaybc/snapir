package il.co.dcd.verification;

/** Report analysis stages without exposing source bodies or configuration values. */
final class AnalysisProgress {
    private static final long START = System.nanoTime();
    private AnalysisProgress() { }
    static void report(String stage) {
        System.err.printf("Boundary progress +%.1fs: %s%n", (System.nanoTime() - START) / 1_000_000_000.0, stage);
        System.err.flush();
    }
}
