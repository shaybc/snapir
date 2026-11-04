package il.co.dcd.verification.harness;

import java.util.*;
import java.lang.reflect.*;
import org.w3c.dom.Element;
import il.co.dcd.verification.fixtures.FixtureResources;

/** Construct original input DTOs using exact public signatures, without executable expressions. */
final class LegacyInputValues {
    private LegacyInputValues() { }
    private static final ThreadLocal<Map<String,List<String>>> observations=ThreadLocal.withInitial(Map::of);
    static void clear(){observations.remove();}
    @SuppressWarnings("unchecked") static void configure(Element job) {
        Element node=BoundaryValues.children(job,"original_context_getters").stream().findFirst().orElse(null);
        observations.set(node==null?Map.of():(Map<String,List<String>>)BoundaryValues.read(node));
    }
    static Object snapshot(String key,Object value) {
        if(!observations.get().containsKey(key))return BoundaryValues.snapshot(value);
        try {return BoundaryValues.snapshot(project(value,observations.get().getOrDefault(key,List.of())));}
        catch(Exception error){throw new BoundaryRuntime.Incomplete("Original Context observation failed: "+key+": "+error);}
    }
    @SuppressWarnings("unchecked") static Map<String,Object> inputs(Element job,Map<String,Object> state)throws Exception {
        Map<String,Object> result=new LinkedHashMap<>(state);
        Map<String,Object> scenario=(Map<String,Object>)BoundaryValues.read(BoundaryValues.child(job,"case"));
        if(((Map<?,?>)scenario.getOrDefault("original_inputs",Map.of())).isEmpty())return result;
        Set<String> allowed=new HashSet<>((List<String>)BoundaryValues.read(BoundaryValues.child(job,"original_types")));
        for(var entry:((Map<String,Map<String,Object>>)scenario.getOrDefault("original_inputs",Map.of())).entrySet())
            result.put(entry.getKey(),value(entry.getValue(),state,allowed,0,null));
        return result;
    }
    private static Class<?> type(String name)throws Exception {
        return switch(name){case "int"->int.class;case "long"->long.class;case "boolean"->boolean.class;case "double"->double.class;default->LegacyBoundaryAdapter.load(name);};
    }
    @SuppressWarnings("unchecked") private static Object value(Map<String,Object> recipe,Map<String,Object> state,Set<String> allowed,int depth,Object item)throws Exception {
        if(depth>12)throw new BoundaryRuntime.Incomplete("Original input nesting limit exceeded");
        String name=(String)recipe.get("type_name"),source=(String)recipe.get("source");Class<?> target=type(name);
        if(source.equals("collection")) {
            Object input=FixtureResources.input((String)recipe.get("key"));
            if(input==null)return null;
            if(!(input instanceof List<?> rows)||!Set.of(List.class,Set.class).contains(target)||!(recipe.get("element") instanceof Map<?,?> element))throw new BoundaryRuntime.Incomplete("Invalid original typed collection recipe");
            List<Object> result=new ArrayList<>();for(Object row:rows)result.add(value((Map<String,Object>)element,state,allowed,depth+1,row));
            return target==Set.class?new LinkedHashSet<>(result):result;
        }
        if(source.equals("fixture")||source.equals("context")||source.equals("item")) {
            String key=(String)recipe.get("key");
            if(source.equals("context")&&!state.containsKey(key))throw new BoundaryRuntime.Incomplete("Missing original Context input: "+key);
            Object input=source.equals("fixture")?FixtureResources.input(key):source.equals("item")?FixtureResources.pointer(item,key):state.get(key);
            if(input==null&&!target.isPrimitive())return null;
            if(target.isInstance(input))return input;
            if(input instanceof Number number) {
                var exact=new java.math.BigDecimal(number.toString());
                if(target==int.class||target==Integer.class)return exact.intValueExact();
                if(target==long.class||target==Long.class)return exact.longValueExact();
            }
            if(target==boolean.class&&input instanceof Boolean)return input;
            throw new BoundaryRuntime.Incomplete("Original fixture type mismatch: "+name);
        }
        if(!source.equals("object")||!allowed.contains(name)||recipe.get("factory_method")!=null)
            throw new BoundaryRuntime.Incomplete("Unsupported original input construction: "+name);
        var arguments=(List<Map<String,Object>>)recipe.get("arguments");Class<?>[] types=new Class<?>[arguments.size()];Object[] values=new Object[arguments.size()];
        for(int i=0;i<values.length;i++){types[i]=type((String)arguments.get(i).get("type_name"));values[i]=value(arguments.get(i),state,allowed,depth+1,item);}
        Constructor<?> constructor=target.getConstructor(types);NativeBoundaryValues.checkArguments(constructor.getGenericParameterTypes(),values);
        Object object=constructor.newInstance(values);
        for(var property:((Map<String,Map<String,Object>>)recipe.get("properties")).entrySet()) {
            Method setter=target.getMethod(property.getKey(),type((String)property.getValue().get("type_name")));
            Object argument=value(property.getValue(),state,allowed,depth+1,item);NativeBoundaryValues.checkArguments(setter.getGenericParameterTypes(),new Object[]{argument});setter.invoke(object,argument);
        }
        return object;
    }
    static Object project(Object value,List<String> getters)throws Exception {
        for(String getter:getters) {
            if(value==null)return null;
            Method method=value.getClass().getMethod(getter);
            if(Modifier.isStatic(method.getModifiers())||method.getReturnType()==void.class)throw new BoundaryRuntime.Incomplete("Observation requires a public value getter");
            value=method.invoke(value);
        }
        return value;
    }
}
