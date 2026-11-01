package il.co.dcd.verification.harness;

/** Trusted reflection wiring failure, distinct from an exception thrown by business code. */
public final class AdapterBindingFailure extends ReflectiveOperationException {
    public AdapterBindingFailure(ReflectiveOperationException cause) { super(cause.toString(),cause); }
}
