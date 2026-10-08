package il.co.dcd.composermapper.model;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class FormatDef {
  private String id;
  private Path sourceFile;
  private TagNode rootTag;
  private final Set<String> referencedXmlTags = new LinkedHashSet<>();
  private final Set<String> referencedMappedJavaClasses = new LinkedHashSet<>();
  private final Set<String> inferredExternalDependencies = new LinkedHashSet<>();
  private final Set<String> serializationFlags = new LinkedHashSet<>();
  private final List<DatabaseLookup> databaseLookups = new ArrayList<>();

  public String getId(){return id;}
  public void setId(String id){this.id=id;}
  public Path getSourceFile(){return sourceFile;}
  public void setSourceFile(Path p){this.sourceFile=p;}
  public TagNode getRootTag(){return rootTag;}
  public void setRootTag(TagNode t){this.rootTag=t;}
  public Set<String> getReferencedXmlTags(){return referencedXmlTags;}
  public Set<String> getReferencedMappedJavaClasses(){return referencedMappedJavaClasses;}
  public Set<String> getInferredExternalDependencies(){return inferredExternalDependencies;}
  public Set<String> getSerializationFlags(){return serializationFlags;}
  public List<DatabaseLookup> getDatabaseLookups(){return databaseLookups;}

  public static class DatabaseLookup {
    private final String nodeName;
    private final String fromTable;
    private final String fromColumn;
    private final String keyValue;

    public DatabaseLookup(String nodeName, String fromTable, String fromColumn, String keyValue) {
      this.nodeName = nodeName;
      this.fromTable = fromTable;
      this.fromColumn = fromColumn;
      this.keyValue = keyValue;
    }

    public String getNodeName(){return nodeName;}
    public String getFromTable(){return fromTable;}
    public String getFromColumn(){return fromColumn;}
    public String getKeyValue(){return keyValue;}
  }
}
