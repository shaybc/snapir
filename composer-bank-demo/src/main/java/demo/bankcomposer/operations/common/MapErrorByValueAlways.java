package demo.bankcomposer.operations.common;

public class MapErrorByValueAlways {
    private String errorCategory;
    private String errorNumber;

    public void setErrorCategory(String errorCategory) {
        this.errorCategory = errorCategory;
    }

    public void setErrorNumber(String errorNumber) {
        this.errorNumber = errorNumber;
    }

    public int execute() {
        return 0;
    }
}

