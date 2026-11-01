package com.ibm.dse.base;

import java.util.ArrayList;
import java.util.List;

/** Demo operation holder; fixture callers register configured steps and a shared context. */
public abstract class DSEServerOperation {
    private Context context = new Context();
    private final List<KeyedCollection> steps = new ArrayList<>();

    public abstract void execute() throws Exception;
    public void setContext(Context context) { this.context = context; }
    public Context getContext() { return context; }
    public void addOperationStep(KeyedCollection step) { steps.add(step); }
    protected List<KeyedCollection> operationSteps() { return steps; }
    protected KeyedCollection getOperationStep(int index) { return steps.get(index); }
}
