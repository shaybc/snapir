package com.ibm.il.dse.cc.cut;

import com.ibm.dse.base.CCOperationStep;

/** Demo nested-operation dispatch sharing the caller's context and return code. */
public class CCComplexOpStep extends CCOperationStep {
    private String opExecuteName;

    public void setOpExecuteName(String opExecuteName) {
        this.opExecuteName = opExecuteName;
    }

    /** Register the target operation executor with setService using its operation name. */
    @Override
    public int execute() throws Exception {
        if (opExecuteName == null || opExecuteName.isBlank()) {
            throw new IllegalStateException("Configure opExecuteName before dispatch");
        }
        CCOperationStep target = (CCOperationStep) getService(opExecuteName);
        target.setContext(getContext());
        return target.execute();
    }
}
