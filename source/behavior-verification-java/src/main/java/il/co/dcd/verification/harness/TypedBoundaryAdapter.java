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
        Map<String, Object> attributes = (Map<String, Object>) BoundaryValues.read(BoundaryValues.child(configuration, "attributes"));
        Object target = null;
        if (!Boolean.TRUE.equals(binding.get("static_method"))) {
            Constructor<?> constructor = owner.getConstructor(NativeBoundaryValues.types(constructors));
            Object[] inputs = NativeBoundaryValues.values(constructors, xml, context, attributes);
            NativeBoundaryValues.checkArguments(constructor.getGenericParameterTypes(), inputs);
            target = constructor.newInstance(inputs);
        }
        Map<String, Map<String, Object>> setters = (Map<String, Map<String, Object>>) binding.getOrDefault("configuration_setters", Map.of());
        for (var setter : setters.entrySet()) {
            Map<String, Object> recipe = setter.getValue();
            if (!"configuration".equals(recipe.get("source"))) throw new BoundaryRuntime.Incomplete("Configuration setters require configuration inputs");
            NativeBoundaryValues.validate(List.of(recipe), nativeTypes);
            if (attributes.containsKey((String) recipe.get("key"))) owner.getMethod(setter.getKey(), NativeBoundaryValues.type((String) recipe.get("type_name")))
                .invoke(target, NativeBoundaryValues.value(recipe, xml, context, attributes));
        }
        Object[] arguments = NativeBoundaryValues.values(recipes, xml, context, attributes);
        Method method = owner.getMethod((String) binding.get("method_name"), NativeBoundaryValues.types(recipes));
        NativeBoundaryValues.checkArguments(method.getGenericParameterTypes(), arguments);
        if (Modifier.isStatic(method.getModifiers()) != Boolean.TRUE.equals(binding.get("static_method")))
            throw new BoundaryRuntime.Incomplete("Native static/instance entry differs from binding");
        Object result = null;
        boolean returned = false;
        try { result = method.invoke(target, arguments); returned = true; }
        finally {
            for (Map<String, Object> projection : (List<Map<String, Object>>) binding.get("context_writes")) {
                Object source = projection.get("source").equals("result") ? result : projection.get("source").equals("receiver") ? target : arguments[((Number) projection.get("argument_index")).intValue()];
                if (!returned && projection.get("source").equals("result")) continue;
                List<String> presence = (List<String>) projection.get("presence_getters");
                if (!presence.isEmpty()) {
                    Object present = NativeBoundaryValues.read(source, presence, nativeTypes);
                    if (!(present instanceof Boolean)) throw new BoundaryRuntime.Incomplete("Presence accessor must return boolean");
                    if (Boolean.FALSE.equals(present)) continue;
                }
                // A result unavailable on failure cannot fabricate the legacy's partial writes.
                if (source == null && !returned) throw new BoundaryRuntime.Incomplete("Native partial state is unavailable after failure");
                Object observed = NativeBoundaryValues.read(source, (List<String>) projection.get("getters"), nativeTypes);
                Map<String,List<String>> fields = (Map<String,List<String>>) projection.getOrDefault("collection_fields", Map.of());
                if (!fields.isEmpty() && observed != null) {
                    if (!(observed instanceof Collection<?> rows)) throw new BoundaryRuntime.Incomplete("Collection observation requires an actual collection");
                    List<Object> projected = new ArrayList<>();
                    for (Object row : rows) {
                        if (row == null) { projected.add(null); continue; }
                        Map<String,Object> values = new LinkedHashMap<>();
                        for (var field : fields.entrySet()) {
                            if (field.getValue().isEmpty()) throw new BoundaryRuntime.Incomplete("Collection field requires a public getter path");
                            values.put(field.getKey(),NativeBoundaryValues.read(row,field.getValue(),nativeTypes));
                        }
                        projected.add(values);
                    }
                    observed = projected;
                }
                context.put((String) projection.get("context_key"), observed);
            }
        }
        return binding.get("output").equals("none") ? null : NativeBoundaryValues.read(result, (List<String>) binding.get("output_getters"), nativeTypes);
    }
}
