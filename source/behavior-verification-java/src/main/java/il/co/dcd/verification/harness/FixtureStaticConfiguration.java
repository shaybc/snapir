package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.util.*;

/** Source-owned public static configuration with actual previous-value restoration per case. */
public final class FixtureStaticConfiguration implements AutoCloseable {
    private record Restore(Method method,Object[] values) {}
    private final List<Restore> restore = new ArrayList<>();
    private FixtureStaticConfiguration() {}

    @SuppressWarnings("unchecked") public static FixtureStaticConfiguration open(List<Map<String,Object>> entries,String xml,Map<String,Object> context,Map<String,Object> configuration) throws Exception {
        FixtureStaticConfiguration scope=new FixtureStaticConfiguration();
        try {
            for(var entry:entries) {
                Class<?> owner=NativeBoundaryValues.type((String)entry.get("owner_type"));
                var recipes=(List<Map<String,Object>>)entry.get("arguments");
                var getters=(List<String>)entry.get("restore_getters");
                if(recipes.size()!=getters.size())throw new BoundaryRuntime.Incomplete("Static setup needs matching restoration getters");
                Method method=owner.getMethod((String)entry.get("method_name"),NativeBoundaryValues.types(recipes));
                if(!Modifier.isStatic(method.getModifiers()))throw new BoundaryRuntime.Incomplete("Fixture setup method must be static");
                Object[] previous=new Object[getters.size()];
                for(int i=0;i<getters.size();i++) {
                    Method getter=owner.getMethod(getters.get(i));
                    if(!Modifier.isStatic(getter.getModifiers()))throw new BoundaryRuntime.Incomplete("Restoration getter must be static");
                    previous[i]=copy(getter.invoke(null));
                }
                NativeBoundaryValues.checkArguments(method.getGenericParameterTypes(),previous);
                Object[] values=NativeBoundaryValues.values(recipes,xml,context,configuration);
                NativeBoundaryValues.checkArguments(method.getGenericParameterTypes(),values);
                scope.restore.add(new Restore(method,previous));
                method.invoke(null,values);
            }
            return scope;
        } catch(Exception failure) {
            try{scope.close();}catch(Exception cleanup){failure.addSuppressed(cleanup);}
            throw failure;
        }
    }

    @Override public void close() throws Exception {
        Exception failure=null;
        for(int i=restore.size()-1;i>=0;i--) {
            Restore item=restore.get(i);
            try{item.method.invoke(null,item.values);}catch(Exception error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        }
        restore.clear();
        if(failure!=null)throw failure;
    }

    private static Object copy(Object value) {
        if(value==null||value instanceof String||value instanceof Number||value instanceof Boolean||value instanceof Character||value instanceof Enum<?>)return value;
        if(value instanceof Set<?> items){Set<Object> out=new LinkedHashSet<>();items.forEach(item->out.add(copy(item)));return out;}
        if(value instanceof List<?> items){List<Object> out=new ArrayList<>();items.forEach(item->out.add(copy(item)));return out;}
        if(value instanceof Map<?,?> items){Map<Object,Object> out=new LinkedHashMap<>();items.forEach((key,item)->out.put(copy(key),copy(item)));return out;}
        throw new BoundaryRuntime.Incomplete("Static fixture configuration has no lossless restoration for "+value.getClass().getName());
    }
}
