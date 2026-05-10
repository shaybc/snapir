package demo.bankcomposer.tags;

public class ContextDefinition {
    private String id;
    private String parent;
    private String type;

    public void setId(String id) {
        this.id = id;
    }

    public void setParent(String parent) {
        this.parent = parent;
    }

    public void setType(String type) {
        this.type = type;
    }

    public int execute() {
        return 0;
    }
}

