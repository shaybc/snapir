package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.util.*;
import il.co.dcd.verification.fixtures.*;

/** Trusted test-only exact public invocation; production code never contains this reflection. */
public final class FixtureInvocation {
    private FixtureInvocation() { }
    @SuppressWarnings("unchecked") public static FixtureResult run(Map<String, Object> binding, String xml, Map<String, Object> context, Map<String,Object> configuration, boolean construct) throws Exception {
        Class<?> owner = NativeBoundaryValues.type((String) binding.get("owner_type"));
        var constructor = (List<Map<String, Object>>) binding.get("constructor_arguments");
        var recipes = (List<Map<String, Object>>) binding.get("arguments");
        Object[] constructorValues=NativeBoundaryValues.values(constructor,xml,context,configuration);
        Object target;
        if (!Boolean.TRUE.equals(binding.get("static_method")))
            NativeBoundaryValues.checkArguments(owner.getConstructor(NativeBoundaryValues.types(constructor)).getGenericParameterTypes(),constructorValues);
        try { target = Boolean.TRUE.equals(binding.get("static_method")) ? null
            : owner.getConstructor(NativeBoundaryValues.types(constructor)).newInstance(constructorValues); }
        catch (InvocationTargetException failure) {
            if (!construct) throw failure;
            Throwable cause=failure.getCause();
            if (cause instanceof BoundaryRuntime.Incomplete incomplete) throw incomplete;
            if (cause instanceof LinkageError error) throw error;
            return new FixtureResult(null,cause,FixtureResources.events(),Arrays.asList(constructorValues));
        }
        if (construct) return new FixtureResult(target,null,FixtureResources.events(),Arrays.asList(constructorValues),target);
        for (var setter : ((Map<String,Map<String,Object>>)binding.get("configuration_setters")).entrySet()) {
            Map<String,Object> recipe=setter.getValue();
            if (!recipe.get("source").equals("configuration")) throw new BoundaryRuntime.Incomplete("Configuration setter requires configuration input");
            owner.getMethod(setter.getKey(),NativeBoundaryValues.type((String)recipe.get("type_name")))
                .invoke(target,NativeBoundaryValues.value(recipe,xml,context,configuration));
        }
        Method method = owner.getMethod((String) binding.get("method_name"), NativeBoundaryValues.types(recipes));
        if (Modifier.isStatic(method.getModifiers()) != Boolean.TRUE.equals(binding.get("static_method"))) throw new BoundaryRuntime.Incomplete("Wrong fixture entry kind");
        Object[] values = NativeBoundaryValues.values(recipes, xml, context, configuration);
        NativeBoundaryValues.checkArguments(method.getGenericParameterTypes(), values);
        try { return new FixtureResult(method.invoke(target, values), null, FixtureResources.events(),Arrays.asList(values),target); }
        catch (InvocationTargetException failure) {
            Throwable cause = failure.getCause();
            if (cause instanceof BoundaryRuntime.Incomplete incomplete) throw incomplete;
            if (cause instanceof LinkageError error) throw error;
            return new FixtureResult(null, cause, FixtureResources.events(),Arrays.asList(values),target);
        }
    }
}
