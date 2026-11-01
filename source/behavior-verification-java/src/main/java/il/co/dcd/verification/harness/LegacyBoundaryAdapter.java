package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.util.*;
import org.w3c.dom.Element;

/** Shared framework binding; component bodies and decorators execute their original supplied code. */
public final class LegacyBoundaryAdapter implements BoundaryAdapter {
    private Object context;
    private Element job;

    void configure(Element job) { this.job = job; }

    @SuppressWarnings("unchecked")
    public Object invoke(String xml, Map<String, Object> state, Element configuration) throws Exception {
        Class<?> contextClass = load(job.getAttribute("context_class"));
        context = contextClass.getConstructor().newInstance();
        for (var entry : state.entrySet()) contextClass.getMethod(job.getAttribute("context_writer"), String.class, Object.class)
            .invoke(context, entry.getKey(), entry.getValue());
        BoundaryRuntime.writes.clear();
        Object component;
        if (job.getAttribute("kind").equals("configured_step")) {
            component = load(job.getAttribute("implementation")).getConstructor().newInstance();
            initialize(component, (Map<String, Object>) BoundaryValues.read(BoundaryValues.child(configuration, "attributes")));
            component.getClass().getMethod(job.getAttribute("step_context_setter"), contextClass).invoke(component, context);
            return call(component.getClass().getMethod("execute"), component);
        }
        component = build(configuration);
        return job.getAttribute("kind").equals("request_unformat")
            ? call(component.getClass().getMethod("unformat", String.class, contextClass), component, xml, context)
            : call(component.getClass().getMethod("format", contextClass), component, context);
    }

    @SuppressWarnings("unchecked")
    Map<String, Object> snapshot(Map<String, Object> initial) throws Exception {
        return context == null ? initial : (Map<String, Object>) context.getClass().getMethod(job.getAttribute("context_snapshot")).invoke(context);
    }

    @SuppressWarnings("unchecked") private Object build(Element node) throws Exception {
        Object component = load(node.getAttribute("implementation")).getConstructor().newInstance();
        initialize(component, (Map<String, Object>) BoundaryValues.read(BoundaryValues.child(node, "attributes")));
        for (Element child : BoundaryValues.children(node, null)) {
            if (child.getTagName().equals("component")) register(component, "addChild", build(child));
            else if (child.getTagName().equals("decorator")) {
                Object decorator = build(child);
                List<Method> targets = Arrays.stream(component.getClass().getMethods()).filter(method ->
                    Set.of("addDecorator", "addAttributeDecorator").contains(method.getName()) && method.getParameterCount() == 1
                    && method.getParameterTypes()[0].isInstance(decorator)).toList();
                if (targets.size() != 1) throw new BoundaryRuntime.Incomplete("Decorator registration is not unique");
                targets.get(0).invoke(component, decorator);
            }
        }
        return component;
    }

    private void initialize(Object component, Map<String, Object> attributes) throws Exception {
        if (Arrays.stream(component.getClass().getMethods()).anyMatch(method -> method.getName().equals("initializeFrom"))) {
            Class<?> tagClass = load(job.getAttribute("tag_class"));
            Method initializer;
            try { initializer = component.getClass().getMethod("initializeFrom", tagClass); }
            catch (NoSuchMethodException absent) { throw new BoundaryRuntime.Incomplete("Initialization signature needs an explicit framework adapter"); }
            initializer.invoke(component, tagClass.getConstructor(Map.class).newInstance(attributes));
            return;
        }
        for (var attribute : attributes.entrySet()) {
            List<Method> setters = Arrays.stream(component.getClass().getMethods()).filter(method -> method.getParameterCount() == 1
                && method.getName().equalsIgnoreCase("set" + attribute.getKey())).toList();
            if (setters.size() > 1) throw new BoundaryRuntime.Incomplete("Ambiguous property setter");
            if (setters.size() == 1) {
                if (attribute.getValue() != null && !setters.get(0).getParameterTypes()[0].isInstance(attribute.getValue()))
                    throw new BoundaryRuntime.Incomplete("Property conversion requires an explicit framework adapter");
                setters.get(0).invoke(component, attribute.getValue());
            }
        }
    }
    private static void register(Object component, String name, Object child) throws Exception {
        List<Method> methods = Arrays.stream(component.getClass().getMethods()).filter(method -> method.getName().equals(name)
            && method.getParameterCount() == 1 && method.getParameterTypes()[0].isInstance(child)).toList();
        if (methods.size() != 1) throw new BoundaryRuntime.Incomplete("Child registration is not unique");
        methods.get(0).invoke(component, child);
    }
    static Class<?> load(String name) throws ClassNotFoundException { return Class.forName(name, true, Thread.currentThread().getContextClassLoader()); }
    private static Object call(Method method, Object receiver, Object... arguments) throws Exception {
        try { return method.invoke(receiver, arguments); }
        catch (InvocationTargetException exception) {
            if (exception.getCause() instanceof Exception cause) throw cause;
            if (exception.getCause() instanceof Error cause) throw cause;
            throw exception;
        }
    }
}
