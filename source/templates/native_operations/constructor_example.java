// Structural example only. Real types, configuration and outcomes come from accepted APIs.
final class ExampleOperation {
    private final ExampleStep check;
    private final ExampleStep perform;

    public ExampleOperation(ExampleStep check, ExampleStep perform) {
        this.check = java.util.Objects.requireNonNull(check);
        this.perform = java.util.Objects.requireNonNull(perform);
    }

    public int execute(int input) {
        int result = this.check.execute(input);
        return result == 0 ? this.perform.execute(input) : result;
    }
}

interface ExampleStep {
    int execute(int input);
}
