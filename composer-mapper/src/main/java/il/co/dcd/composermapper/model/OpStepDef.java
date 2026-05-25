package il.co.dcd.composermapper.model;

import java.nio.file.Path;
import java.util.*;

public class OpStepDef {
    private String id;
    private String parentOperationId;
    private String implClass;
    private Path   sourceFile;
    /** Channel name(s) this step is restricted to via onlyFor attribute. Null = all channels. */
    private String onlyFor;
    private final Map<String,String> rawAttributes      = new LinkedHashMap<>();
    private final Map<String,String> transitions        = new LinkedHashMap<>();
    /** on{N}Return entries: returnCode → formatName to switch reply body to */
    private final Map<String,String> returnBodySwitches = new LinkedHashMap<>();
    private final Map<String,String> parameters         = new LinkedHashMap<>();

    public String getId()                               { return id; }
    public void   setId(String id)                      { this.id = id; }
    public String getParentOperationId()                { return parentOperationId; }
    public void   setParentOperationId(String v)        { this.parentOperationId = v; }
    public String getImplClass()                        { return implClass; }
    public void   setImplClass(String v)                { this.implClass = v; }
    public Path   getSourceFile()                       { return sourceFile; }
    public void   setSourceFile(Path p)                 { this.sourceFile = p; }
    public String getOnlyFor()                          { return onlyFor; }
    public void   setOnlyFor(String v)                  { this.onlyFor = v; }
    public Map<String,String> getRawAttributes()        { return rawAttributes; }
    public Map<String,String> getTransitions()          { return transitions; }
    public Map<String,String> getReturnBodySwitches()   { return returnBodySwitches; }
    public Map<String,String> getParameters()           { return parameters; }
}
