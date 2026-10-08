package il.co.dcd.composermapper.model;

import java.nio.file.Path;
import java.util.*;

public class OperationDef {
    private String id;
    private String operationContext;
    private Path   sourceFile;
    // operation-level attributes from CCDSEServerOperation tag
    private String hostKey;
    private String operationFields;
    private String writeToLog;
    private String writeToOfecStat;
    private String isSelectiveJournalising;
    private final List<String>         iniValues         = new ArrayList<>();
    private final Map<String,String>   rawAttributes     = new LinkedHashMap<>();
    private final List<OpStepDef>      steps             = new ArrayList<>();
    private final Map<String,String>   refFormats        = new LinkedHashMap<>();
    private final List<String>         inlineFormatIds   = new ArrayList<>();

    public String getId()                               { return id; }
    public void   setId(String id)                      { this.id = id; }
    public String getOperationContext()                 { return operationContext; }
    public void   setOperationContext(String v)         { this.operationContext = v; }
    public Path   getSourceFile()                       { return sourceFile; }
    public void   setSourceFile(Path p)                 { this.sourceFile = p; }
    public String getHostKey()                          { return hostKey; }
    public void   setHostKey(String v)                  { this.hostKey = v; }
    public String getOperationFields()                  { return operationFields; }
    public void   setOperationFields(String v)          { this.operationFields = v; }
    public String getWriteToLog()                       { return writeToLog; }
    public void   setWriteToLog(String v)               { this.writeToLog = v; }
    public String getWriteToOfecStat()                  { return writeToOfecStat; }
    public void   setWriteToOfecStat(String v)          { this.writeToOfecStat = v; }
    public String getIsSelectiveJournalising()          { return isSelectiveJournalising; }
    public void   setIsSelectiveJournalising(String v)  { this.isSelectiveJournalising = v; }
    public List<String>         getIniValues()          { return iniValues; }
    public Map<String,String>   getRawAttributes()      { return rawAttributes; }
    public List<OpStepDef>      getSteps()              { return steps; }
    public Map<String,String>   getRefFormats()         { return refFormats; }
    public List<String>         getInlineFormatIds()    { return inlineFormatIds; }
}
