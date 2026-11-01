package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.util.*;
import org.w3c.dom.Element;

/** Converter-owned bridge: invoke the declared native API and project its actual typed state. */
public final class TypedBoundaryAdapter implements BoundaryAdapter {
    @SuppressWarnings("unchecked") public Object invoke(String xml, Map<String, Object> context, Element configuration) throws Exception {
        try { return invokeBound(xml,context,configuration); }
        catch (InvocationTargetException businessFailure) { throw businessFailure; }
        catch (ReflectiveOperationException wiringFailure) { throw new AdapterBindingFailure(wiringFailure); }
    }

    @SuppressWarnings("unchecked") private Object invokeBound(String xml, Map<String, Object> context, Element configuration) throws Exception {
        Element entry = BoundaryValues.child(configuration, "native_entry");
        if (entry == null) throw new BoundaryRuntime.Incomplete("Native boundary entry is missing");
        Map<String, Object> binding = (Map<String, Object>) BoundaryValues.read(entry);
        Set<String> nativeTypes = new HashSet<>((List<String>) binding.get("native_types"));
        if (!nativeTypes.contains((String) binding.get("owner_type")))
            throw new BoundaryRuntime.Incomplete("Boundary owner must be an actual supplied native type");
        Class<?> owner = NativeBoundaryValues.type((String) binding.get("owner_type"));
        List<Map<String, Object>> constructors = (List<Map<String, Object>>) binding.get("constructor_arguments");
        List<Map<String, Object>> recipes = (List<Map<String, Object>>) binding.get("arguments");
        NativeBoundaryValues.validate(constructors, nativeTypes);
        NativeBoundaryValues.validate(recipes, nativeTypes);
        Object target = Boolean.TRUE.equals(binding.get("static_method")) ? null : owner.getConstructor(NativeBoundaryValues.types(constructors))
            .newInstance(NativeBoundaryValues.values(constructors, xml, context));
        Object[] arguments = NativeBoundaryValues.values(recipes, xml, context);
        Method method = owner.getMethod((String) binding.get("method_name"), NativeBoundaryValues.types(recipes));
        if (Modifier.isStatic(method.getModifiers()) != Boolean.TRUE.equals(binding.get("static_method")))
            throw new BoundaryRuntime.Incomplete("Native static/instance entry differs from binding");
        Object result = null;
        boolean returned = false;
        try { result = method.invoke(target, arguments); returned = true; }
        finally {
            for (Map<String, Object> projection : (List<Map<String, Object>>) binding.get("context_writes")) {
                Object source = projection.get("source").equals("result") ? result : arguments[((Number) projection.get("argument_index")).intValue()];
                if (!returned && projection.get("source").equals("result")) continue;
                List<String> presence = (List<String>) projection.get("presence_getters");
                if (!presence.isEmpty()) {
                    Object present = NativeBoundaryValues.read(source, presence, nativeTypes);
                    if (!(present instanceof Boolean)) throw new BoundaryRuntime.Incomplete("Presence accessor must return boolean");
                    if (Boolean.FALSE.equals(present)) continue;
                }
                // A result unavailable on failure cannot fabricate the legacy's partial writes.
                if (source == null) throw new BoundaryRuntime.Incomplete("Native partial state is unavailable after failure");
                context.put((String) projection.get("context_key"), NativeBoundaryValues.read(source, (List<String>) projection.get("getters"), nativeTypes));
            }
        }
        return binding.get("output").equals("none") ? null : NativeBoundaryValues.read(result, (List<String>) binding.get("output_getters"), nativeTypes);
    }
}
