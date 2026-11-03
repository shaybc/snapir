package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.util.*;

/** Strict typed argument construction; no evaluated expressions, constants or framework recreation. */
final class NativeBoundaryValues {
    private NativeBoundaryValues() { }

    @SuppressWarnings("unchecked") static void validate(List<Map<String, Object>> recipes, Set<String> nativeTypes) {
        Set<String> scalars = Set.of("java.lang.String", "java.lang.Integer", "java.lang.Long", "java.lang.Boolean", "java.lang.Double",
            "java.math.BigDecimal", "java.util.Date", "int", "long", "boolean", "double", "float", "short", "byte", "char", "java.util.List");
        for (Map<String, Object> recipe : recipes) {
            String name = (String) recipe.get("type_name");
            if (recipe.get("source").equals("object") ? !nativeTypes.contains(name) : !scalars.contains(name) && !nativeTypes.contains(name))
                throw new BoundaryRuntime.Incomplete("Boundary arguments require native types or controlled scalars");
            validate((List<Map<String, Object>>) recipe.get("arguments"), nativeTypes);
            validate(new ArrayList<>(((Map<String, Map<String, Object>>) recipe.get("properties")).values()), nativeTypes);
        }
    }

    static Class<?> type(String name) throws ClassNotFoundException {
        if (name.startsWith("com.ibm.") || name.equals("java.util.Map") || name.endsWith("Context"))
            throw new BoundaryRuntime.Incomplete("Unsupported native boundary type: " + name);
        return switch (name) {
            case "int" -> int.class; case "long" -> long.class; case "boolean" -> boolean.class;
            case "double" -> double.class; case "float" -> float.class; case "short" -> short.class;
            case "byte" -> byte.class; case "char" -> char.class; default -> LegacyBoundaryAdapter.load(name);
        };
    }

    @SuppressWarnings("unchecked") static Object value(Map<String, Object> recipe, String xml, Map<String, Object> context, Map<String, Object> configuration) throws Exception {
        Class<?> target = type((String) recipe.get("type_name"));
        String source = (String) recipe.get("source");
        if (source.equals("xml")) {
            if (target != String.class) throw new BoundaryRuntime.Incomplete("XML boundary input must be a native String facade");
            return xml;
        }
        if (source.equals("context") || source.equals("configuration")) {
            Object value = (source.equals("context") ? context : configuration).get((String) recipe.get("key"));
            if (value == null && target.isPrimitive()) throw new BoundaryRuntime.Incomplete("Missing primitive native argument");
            if (value == null || target.isInstance(value)) return value;
            if (value instanceof Number number) {
                java.math.BigDecimal exact = new java.math.BigDecimal(number.toString());
                if (target == int.class || target == Integer.class) return exact.intValueExact();
                if (target == long.class || target == Long.class) return exact.longValueExact();
                if (target == double.class || target == Double.class) return number.doubleValue();
            }
            if (value instanceof Boolean && target == boolean.class) return value;
            throw new BoundaryRuntime.Incomplete("No implicit string/number conversion in boundary adapter");
        }
        if (!source.equals("object")) throw new BoundaryRuntime.Incomplete("Unknown native argument recipe");
        List<Map<String, Object>> arguments = (List<Map<String, Object>>) recipe.get("arguments");
        Object factoryName = recipe.get("factory_method");
        Object object;
        if (factoryName == null) {
            Constructor<?> constructor = target.getConstructor(types(arguments));
            Object[] inputs = values(arguments, xml, context, configuration);
            checkArguments(constructor.getGenericParameterTypes(), inputs);
            object = constructor.newInstance(inputs);
        }
        else {
            Method factory = target.getMethod((String) factoryName, types(arguments));
            if (!Modifier.isStatic(factory.getModifiers()) || factory.getReturnType() != target)
                throw new BoundaryRuntime.Incomplete("Native DTO factory must be static and return its declared type");
            Object[] inputs = values(arguments, xml, context, configuration);
            checkArguments(factory.getGenericParameterTypes(), inputs);
            object = factory.invoke(null, inputs);
        }
        Map<String, Map<String, Object>> properties = (Map<String, Map<String, Object>>) recipe.get("properties");
        for (var entry : properties.entrySet()) {
            Method setter = target.getMethod(entry.getKey(), type((String) entry.getValue().get("type_name")));
            Object[] inputs = {value(entry.getValue(), xml, context, configuration)};
            checkArguments(setter.getGenericParameterTypes(), inputs);
            setter.invoke(object, inputs);
        }
        return object;
    }

    static Class<?>[] types(List<Map<String, Object>> recipes) throws Exception {
        Class<?>[] result = new Class<?>[recipes.size()];
        for (int i = 0; i < result.length; i++) result[i] = type((String) recipes.get(i).get("type_name"));
        return result;
    }
    static Object[] values(List<Map<String, Object>> recipes, String xml, Map<String, Object> context) throws Exception {
        return values(recipes, xml, context, Map.of());
    }
    static Object[] values(List<Map<String, Object>> recipes, String xml, Map<String, Object> context, Map<String, Object> configuration) throws Exception {
        Object[] result = new Object[recipes.size()];
        for (int i = 0; i < result.length; i++) result[i] = value(recipes.get(i), xml, context, configuration);
        return result;
    }
    static Object read(Object value, List<String> getters, Set<String> nativeTypes) throws Exception {
        for (String getter : getters) {
            if (value == null) throw new BoundaryRuntime.Incomplete("Native result path reaches null");
            Method method = value.getClass().getMethod(getter);
            if (!nativeTypes.contains(method.getDeclaringClass().getName()))
                throw new BoundaryRuntime.Incomplete("Only native declared accessors may project boundary values");
            value = method.invoke(value);
        }
        return value;
    }

    static void checkArguments(Type[] declared, Object[] values) {
        for (int index = 0; index < declared.length; index++) checkValue(declared[index], values[index]);
    }

    private static void checkValue(Type declared, Object value) {
        if (value == null) return;
        if (declared instanceof ParameterizedType generic) {
            if (value instanceof List<?> items && generic.getRawType() instanceof Class<?> raw && List.class.isAssignableFrom(raw)) {
                for (Object item : items) checkValue(generic.getActualTypeArguments()[0], item);
            } else if (value instanceof Map<?, ?> items && generic.getRawType() instanceof Class<?> raw && Map.class.isAssignableFrom(raw)) {
                for (var item : items.entrySet()) {
                    checkValue(generic.getActualTypeArguments()[0], item.getKey());
                    checkValue(generic.getActualTypeArguments()[1], item.getValue());
                }
            }
        } else if (declared instanceof Class<?> type) {
            if (!type.isPrimitive() && !type.isInstance(value))
                throw new BoundaryRuntime.Incomplete("Native generic input shape requires " + type.getName() + "; adapter cannot invent a conversion");
        } else {
            throw new BoundaryRuntime.Incomplete("Native generic input type is unresolved; an explicit supported binding is required");
        }
    }
}
