package demo.bankcomposer.formats;

public abstract class BaseFormatTag {
    private String dataName;

    public void setDataName(String dataName) {
        this.dataName = dataName;
    }

    public int execute() {
        return 0;
    }
}

