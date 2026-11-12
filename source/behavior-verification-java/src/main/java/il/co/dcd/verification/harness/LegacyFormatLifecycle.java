package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.util.*;
import org.w3c.dom.Element;

/** Invoke only the source-resolved original lifecycle using explicit fixture inputs. */
final class LegacyFormatLifecycle {
    private LegacyFormatLifecycle() { }
    @SuppressWarnings("unchecked")
    static Object invoke(Element job, Object component, Object context, String xml, Element configuration) throws Exception {
        Element lifecycle = BoundaryValues.child(job,"format_lifecycle");
        Map<String,Object> attributes = (Map<String,Object>) BoundaryValues.read(BoundaryValues.child(configuration,"attributes"));
        Object result = null;
        for (Element invocation : BoundaryValues.children(lifecycle,"invocation")) {
            Method method;
            Object[] arguments;
            try {
                List<Element> parameters = BoundaryValues.children(invocation,"parameter");
                Class<?>[] types = new Class<?>[parameters.size()];
                arguments = new Object[types.length];
                for (int i=0;i<types.length;i++) {
                    types[i] = LegacyBoundaryAdapter.load(parameters.get(i).getAttribute("type"));
                    if (types[i] == String.class) arguments[i] = xml;
                    else if (types[i].getSimpleName().equals("Context") && types[i].isInstance(context)) arguments[i] = context;
                    else if (types[i].getSimpleName().equals("FormatElement") && types[i].isInstance(component)) arguments[i] = component;
                    else {
                        String key = "lifecycle:" + types[i].getName();
                        Object supplied = read(job, context, key);
                        if (supplied == null && Set.of("DataField","DataElement").contains(types[i].getSimpleName()) && attributes.get("dataName") instanceof String field)
                            supplied = read(job,context,field);
                        if (!types[i].isInstance(supplied))
                            throw new BoundaryRuntime.Incomplete("Original format lifecycle requires explicit input " + key + " (or dataName field for DataField/DataElement)");
                        arguments[i] = supplied;
                    }
                }
                Class<?> owner = LegacyBoundaryAdapter.load(invocation.getAttribute("declaring_class"));
                if (!owner.isInstance(component)) throw new BoundaryRuntime.Incomplete("Lifecycle receiver does not match configured implementation");
                method = owner.getDeclaredMethod(invocation.getAttribute("method"),types);
                if (Modifier.isStatic(method.getModifiers())) throw new BoundaryRuntime.Incomplete("Format lifecycle cannot invoke a static method");
                method.setAccessible(true);
            } catch (ReflectiveOperationException | IllegalArgumentException | SecurityException failure) {
                throw new BoundaryRuntime.Incomplete("Original format lifecycle binding failed: " + failure);
            }
            try { result = method.invoke(component,arguments); }
            catch (InvocationTargetException exception) {
                if (exception.getCause() instanceof Exception cause) throw cause;
                if (exception.getCause() instanceof Error cause) throw cause;
                throw exception;
            }
        }
        return result;
    }
    private static Object read(Element job,Object context,String key) throws Exception {
        try {
            return context.getClass().getMethod(job.getAttribute("context_reader"),String.class).invoke(context,key);
        } catch (InvocationTargetException failure) {
            throw new BoundaryRuntime.Incomplete("Original format lifecycle requires explicit input " + key
                + "; context lookup failed: " + failure.getCause());
        }
    }
}
