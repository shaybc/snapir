package il.co.dcd.verification;

import java.io.BufferedOutputStream;
import java.io.FilterOutputStream;
import java.io.IOException;
import java.io.OutputStream;

/** Batch XML writes and report bytes actually passed to the destination stream. */
final class BufferedAnalysisOutput extends BufferedOutputStream {
    private static final class Destination extends FilterOutputStream {
        private long bytes, writes, lastReport = System.nanoTime();
        Destination(OutputStream output) { super(output); }
        public void write(int value) throws IOException {
            out.write(value);
            record(1);
        }
        public void write(byte[] values, int offset, int length) throws IOException {
            out.write(values, offset, length);
            record(length);
        }
        private void record(int length) {
            bytes += length;
            writes++;
            if (System.nanoTime() - lastReport >= 5_000_000_000L) {
                report();
                lastReport = System.nanoTime();
            }
        }
        void report() { AnalysisProgress.report("XML output bytes=" + bytes + "; destination writes=" + writes); }
    }
    BufferedAnalysisOutput(OutputStream output) { super(new Destination(output), 64 * 1024); }
    public void close() throws IOException {
        super.close();
        ((Destination) out).report();
    }
}
