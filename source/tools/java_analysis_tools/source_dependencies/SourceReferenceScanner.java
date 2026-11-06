import java.lang.reflect.InvocationTargetException;

/** Compatibility entry point; syntax extraction lives in the shared analysis core. */
public final class SourceReferenceScanner {
    public static void main(String[] args) throws Exception {
        try {
            Class.forName("il.co.dcd.javaanalysis.ReferenceScanMain").getMethod("main",String[].class).invoke(null,(Object)args);
        } catch (InvocationTargetException error) {
            if(error.getCause() instanceof Exception cause)throw cause;
            throw error;
        }
    }
}
