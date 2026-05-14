package il.co.dcd.composermapper.model;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public class OpStepDef {
  private String id;
  private String parentOperationId;
  private String implClass;
  private Path sourceFile;
  private final Map<String, String> rawAttributes = new LinkedHashMap<>();
  private final Map<String, String> transitions = new LinkedHashMap<>();
  private final Map<String, String> parameters = new LinkedHashMap<>();

  public String getId(){return id;}
  public void setId(String id){this.id=id;}
  public String getParentOperationId(){return parentOperationId;}
  public void setParentOperationId(String v){this.parentOperationId=v;}
  public String getImplClass(){return implClass;}
  public void setImplClass(String v){this.implClass=v;}
  public Path getSourceFile(){return sourceFile;}
  public void setSourceFile(Path p){this.sourceFile=p;}
  public Map<String,String> getRawAttributes(){return rawAttributes;}
  public Map<String,String> getTransitions(){return transitions;}
  public Map<String,String> getParameters(){return parameters;}
}
