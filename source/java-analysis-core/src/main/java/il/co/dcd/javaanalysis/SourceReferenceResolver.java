package il.co.dcd.javaanalysis;

import java.util.*;

/** Static source identity policy corresponding to the converter's compatibility resolver. */
public final class SourceReferenceResolver {
    public record Imported(String name, boolean isStatic) {}
    public record Scope(String path,String packageName,List<Imported> imports,Set<String> variables,
                        Set<String> parameters,Set<String> localTypes,Set<String> methods) {}
    public record Result(List<String> targets,String issue) {}
    private SourceReferenceResolver() {}
    public static Result resolve(String name,String kind,Scope scope,TypeLookup lookup) {
        Set<String> variables=new HashSet<>(scope.variables());variables.addAll(List.of("this","super"));
        List<String> names=new ArrayList<>();
        if(kind.equals("qualifier")&&variables.contains(name.split("\\.")[0]))return new Result(List.of(),null);
        if(kind.equals("static_member")||kind.equals("static_field")) {
            if(variables.contains(name)||kind.equals("static_member")&&scope.methods().contains(name))return new Result(List.of(),null);
            for(var imported:scope.imports())if(imported.isStatic()&&(imported.name().endsWith("."+name)||imported.name().endsWith(".*")))
                names.add(imported.name().substring(0,imported.name().lastIndexOf('.')));
        } else {
            if(scope.parameters().contains(name)||scope.localTypes().contains(name)||!name.matches("[\\p{L}\\p{Nl}\\p{No}_$][\\p{L}\\p{N}_$]*(\\.[\\p{L}\\p{Nl}\\p{No}_$][\\p{L}\\p{N}_$]*)*"))return new Result(List.of(),null);
            int dot=name.indexOf('.');String head=dot<0?name:name.substring(0,dot),tail=dot<0?"":name.substring(dot);
            for(var imported:scope.imports())if(!imported.isStatic()&&!imported.name().endsWith(".*")&&imported.name().substring(imported.name().lastIndexOf('.')+1).equals(head))names.add(imported.name()+tail);
            if(names.isEmpty()) {
                String same=(scope.packageName().isEmpty()?"":scope.packageName()+".")+name;
                if(lookup.contains(name)||lookup.contains(same))names.add(lookup.contains(name)?name:same);
                else {names.add(name);names.add(same);for(var imported:scope.imports())if(!imported.isStatic()&&imported.name().endsWith(".*"))names.add(imported.name().substring(0,imported.name().length()-1)+name);}
            }
        }
        Set<String> enclosing=new LinkedHashSet<>();
        for(String candidate:names)while(!candidate.isEmpty()) {
            if(lookup.contains(candidate)){enclosing.add(candidate);break;}
            int dot=candidate.lastIndexOf('.');candidate=dot<0?"":candidate.substring(0,dot);
        }
        var targets=lookup.eligible(enclosing,scope.path());
        if(targets.size()>1)return new Result(List.of(),"Ambiguous Java source reference: "+name);
        if(targets.isEmpty()&&lookup.existsOutsideVisibility(enclosing,scope.path()))return new Result(List.of(),"Java source reference is outside declared project visibility: "+name);
        return new Result(targets,null);
    }
}
