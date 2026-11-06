package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.model.JavaClassDef;
import java.nio.file.Path;

/** Adapt canonical AST metadata to the unchanged documentary writer model. */
final class StoredJavaMetadata {
    private StoredJavaMetadata(){}
    static JavaClassDef read(AnalysisStore store,Path path){
        var rows=store.rows("SELECT fqcn,package,simple_name,parent FROM java_classes WHERE file=?",path.toString());
        if(rows.isEmpty())return null;var row=rows.getFirst();
        var result=new JavaClassDef();result.setSourceFile(path);result.setFullyQualifiedName(row[0]);result.setPackageName(row[1]);result.setSimpleName(row[2]);result.setParentClass(row[3].isBlank()?null:row[3]);
        for(var fact:store.sequence("java_facts","file=? AND (kind='import' OR kind LIKE 'metadata:%')",new Object[]{path.toString()},"kind,name,value",value->value)) {
            String value=fact[1];
            switch(fact[0]) {
                case "import" -> {if(!fact[2].equals("true"))result.getImports().add(value);}
                case "metadata:interface" -> result.getInterfaces().add(value);
                case "metadata:method" -> result.getMethodNames().add(value);
                case "metadata:setter" -> result.getSetterNames().add(value);
                case "metadata:exception" -> result.getThrownExceptions().add(value);
                case "metadata:return" -> result.addReturnCode(value,fact[2]);
                case "metadata:behavior" -> result.getBehaviorTypes().add(value);
                case "metadata:external" -> result.getInferredExternalDependencies().add(value);
            }
        }
        return result;
    }
}
