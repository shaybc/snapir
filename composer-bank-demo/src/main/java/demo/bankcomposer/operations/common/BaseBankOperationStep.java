package demo.bankcomposer.operations.common;

/**
 * Demo base class for Composer opStep implementations.
 * Return codes: 0 success, 4 not found, 5 invalid request, 9 unexpected error.
 */
public abstract class BaseBankOperationStep {
    private String sourceSystem;
    private String entity;

    public void setSourceSystem(String sourceSystem) {
        this.sourceSystem = sourceSystem;
    }

    public void setEntity(String entity) {
        this.entity = entity;
    }

    protected String getSourceSystem() {
        return sourceSystem;
    }

    protected String getEntity() {
        return entity;
    }

    public int execute() {
        return 0;
    }
}

