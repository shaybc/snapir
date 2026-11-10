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
        prepareContext(state);
        Object component;
        if (job.getAttribute("kind").equals("configured_step")) {
            component = load(job.getAttribute("implementation")).getConstructor().newInstance();
            initialize(component, (Map<String, Object>) BoundaryValues.read(BoundaryValues.child(configuration, "attributes")));
            component.getClass().getMethod(job.getAttribute("step_context_setter"), context.getClass()).invoke(component, context);
            return call(component.getClass().getMethod("execute"), component);
        }
        component = prepared(configuration);
        if (!BoundaryValues.children(job,"format_lifecycle").isEmpty())
            return LegacyFormatLifecycle.invoke(job,component,context,xml,configuration);
        return job.getAttribute("kind").equals("request_unformat")
            ? call(component.getClass().getMethod("unformat", String.class, context.getClass()), component, xml, context)
            : call(component.getClass().getMethod("format", context.getClass()), component, context);
    }

    @SuppressWarnings("unchecked") private void prepareContext(Map<String,Object> state) throws Exception {
        if(!job.getAttribute("kind").equals("configured_step"))LegacyInputValues.configure(job);
        Class<?> contextClass;
        try {
            contextClass = load(job.getAttribute("context_class"));
            context = contextClass.getConstructor().newInstance();
            Map<String,Object> populated=job.getAttribute("kind").equals("configured_step")?state:LegacyInputValues.inputs(job,state);
            for (var entry : populated.entrySet()) contextClass.getMethod(job.getAttribute("context_writer"), String.class, Object.class)
                .invoke(context, entry.getKey(), entry.getValue());
            Element values = BoundaryValues.child(job, "case");
            Map<String, Object> input = (Map<String, Object>) BoundaryValues.read(values);
            Map<String, Object> assets = (Map<String, Object>) input.getOrDefault("test_assets", Map.of());
            for (var setter : ((Map<String, String>) assets.getOrDefault("composer_resource_setters", Map.of())).entrySet()) {
                Object resource = il.co.dcd.verification.fixtures.FixtureResources.resource(setter.getValue());
                List<Method> matches = Arrays.stream(contextClass.getMethods()).filter(method -> method.getName().equals(setter.getKey())
                    && method.getParameterCount()==1 && method.getParameterTypes()[0].isInstance(resource)).toList();
                if (matches.size()!=1) throw new BoundaryRuntime.Incomplete("Composer resource setter is missing or ambiguous");
                matches.get(0).invoke(context, resource);
            }
        } catch (ReflectiveOperationException | RuntimeException setupFailure) {
            throw new BoundaryRuntime.Incomplete("Composer context setup failed: " + setupFailure.getClass().getSimpleName());
        }
        BoundaryRuntime.writes.clear();
    }

    Object invokeDecorator(Map<String,Object> state,Element configuration) throws Exception {
        prepareContext(state);Object component=prepared(configuration);
        @SuppressWarnings("unchecked") Map<String,Object> input=(Map<String,Object>)BoundaryValues.read(BoundaryValues.child(job,"case"));
        Object value=input.get("decorator_value");String action=job.getAttribute("original_action");
        if(action.equals("formatXmlAttributes"))return call(component.getClass().getMethod(action,context.getClass(),String.class),component,context,value);
        if(!Set.of("addDecoration","removeDecoration").contains(action))throw new BoundaryRuntime.Incomplete("Unsupported decorator interface");
        return call(component.getClass().getMethod(action,String.class),component,value);
    }

    private Object prepared(Element configuration) {
        try {return build(configuration);}
        catch(Exception error) {
            Throwable reason=error;
            while(reason instanceof InvocationTargetException call && call.getCause()!=null)reason=call.getCause();
            throw new BoundaryRuntime.Incomplete("Original format/decorator initialization failed: "+reason);
        }
    }

    @SuppressWarnings("unchecked")
    Map<String, Object> snapshot(Map<String, Object> initial) throws Exception {
        Map<String,Object> result=context == null ? initial : (Map<String, Object>) context.getClass().getMethod(job.getAttribute("context_snapshot")).invoke(context);
        if(job.getAttribute("kind").equals("configured_step"))return result;
        Element projections=BoundaryValues.children(job,"original_context_getters").stream().findFirst().orElse(null);
        if(projections!=null) {
            result=new LinkedHashMap<>(result);
            for(var entry:((Map<String,List<String>>)BoundaryValues.read(projections)).entrySet()) {
                if(!result.containsKey(entry.getKey()))throw new BoundaryRuntime.Incomplete("Missing original observation key: "+entry.getKey());
                result.put(entry.getKey(),LegacyInputValues.project(result.get(entry.getKey()),entry.getValue()));
            }
        }
        return result;
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
