package il.co.dcd.composermapper.util;

import il.co.dcd.composermapper.model.OpStepDef;
import java.util.List;

/** Resolves transitions over ordered, channel-selected step occurrences. */
public final class OperationStepFlow {
    private final List<OpStepDef> steps;

    /** Captures the effective flow without changing source step labels or order. */
    public OperationStepFlow(List<OpStepDef> steps) { this.steps = List.copyOf(steps); }

    /** Returns the zero-based position of an exact scoped occurrence. */
    public int position(OpStepDef step) {
        for (int i = 0; i < steps.size(); i++) {
            if (steps.get(i).getOccurrenceKey().equals(step.getOccurrenceKey())) return i;
        }
        return -1;
    }

    /**
     * Resolves a transition from its source position, searching inclusively then wrapping.
     * Named labels match exactly; next/end follow the execution method's reserved values.
     * @return the selected occurrence, or null for termination or a missing named target
     */
    public OpStepDef target(OpStepDef source, String name) {
        int start = position(source);
        if (start < 0 || "end".equals(name)) return null;
        if ("next".equalsIgnoreCase(name)) return start + 1 < steps.size() ? steps.get(start + 1) : null;
        for (int i = start; i < steps.size(); i++) if (steps.get(i).getId().equals(name)) return steps.get(i);
        for (int i = 0; i < start; i++) if (steps.get(i).getId().equals(name)) return steps.get(i);
        return null;
    }
}
