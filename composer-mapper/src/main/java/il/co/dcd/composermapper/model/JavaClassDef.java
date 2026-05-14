package il.co.dcd.composermapper.model;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

public class JavaClassDef {
  private String packageName;
  private String simpleName;
  private String fullyQualifiedName;
  private Path sourceFile;
  private final Set<String> imports = new LinkedHashSet<>();
  private final Set<String> methodNames = new LinkedHashSet<>();
  private final Set<String> setterNames = new LinkedHashSet<>();
  private final Set<String> inferredExternalDependencies = new LinkedHashSet<>();
  private final Set<String> behaviorTypes = new LinkedHashSet<>();
  private final Set<String> thrownExceptions = new LinkedHashSet<>();
  private final Map<String, ReturnCode> returnCodes = new LinkedHashMap<>();

  public String getPackageName(){return packageName;}
  public void setPackageName(String v){this.packageName=v;}
  public String getSimpleName(){return simpleName;}
  public void setSimpleName(String v){this.simpleName=v;}
  public String getFullyQualifiedName(){return fullyQualifiedName;}
  public void setFullyQualifiedName(String v){this.fullyQualifiedName=v;}
  public Path getSourceFile(){return sourceFile;}
  public void setSourceFile(Path p){this.sourceFile=p;}
  public Set<String> getImports(){return imports;}
  public Set<String> getMethodNames(){return methodNames;}
  public Set<String> getSetterNames(){return setterNames;}
  public Set<String> getInferredExternalDependencies(){return inferredExternalDependencies;}
  public Set<String> getBehaviorTypes(){return behaviorTypes;}
  public Set<String> getThrownExceptions(){return thrownExceptions;}
  public Map<String, ReturnCode> getReturnCodes(){return returnCodes;}

  public void addReturnCode(String code, String meaning) {
    if (code == null || code.isBlank()) return;
    returnCodes.computeIfAbsent(code, ReturnCode::new).addMeaning(meaning);
  }

  public static class ReturnCode {
    private final String code;
    private final Set<String> meanings = new LinkedHashSet<>();

    public ReturnCode(String code) {
      this.code = code;
    }

    public String getCode(){return code;}
    public Set<String> getMeanings(){return meanings;}

    public void addMeaning(String meaning) {
      if (meaning != null && !meaning.isBlank()) meanings.add(meaning);
    }
  }
}
