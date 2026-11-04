package il.co.dcd.verification.harness;

import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.stream.XMLOutputFactory;
import org.w3c.dom.Element;

/** Run one side of one case in a fresh JVM; no Composer server or shared mutable case state. */
public final class BoundaryHarness {
    private BoundaryHarness() { }

    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element job = factory.newDocumentBuilder().parse(Path.of(args[0]).toFile()).getDocumentElement();
        Map<String, Object> input = (Map<String, Object>) BoundaryValues.read(BoundaryValues.child(job, "case"));
        BoundaryRuntime.reset(input);
        Map<String, Object> initial = (Map<String, Object>) input.get("initial_context");
        var context = new BoundaryRuntime.ContextMap(initial);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("case_id", input.get("case_id")); result.put("status", "completed");
        result.put("invocation_completed", false);
        BoundaryAdapter adapter = null;
        boolean invoked = false;
        try {
            for (Map<String, Object> setting : (List<Map<String, Object>>) input.get("settings")) settings(setting);
            adapter = (BoundaryAdapter) LegacyBoundaryAdapter.load(job.getAttribute("adapter_class")).getConstructor().newInstance();
            if (adapter instanceof LegacyBoundaryAdapter legacy) legacy.configure(job);
            if (adapter instanceof LegacyDecoratorAdapter decorator) decorator.configure(job);
            invoked = true;
            Object returned=adapter.invoke((String) input.get("input_xml"), context, BoundaryValues.child(job, "configuration").getFirstChild() instanceof Element element
                ? element : BoundaryValues.children(BoundaryValues.child(job, "configuration"), null).get(0));
            Element getters=BoundaryValues.children(job,"original_output_getters").stream().findFirst().orElse(null);
            if(getters!=null&&(adapter instanceof LegacyBoundaryAdapter||adapter instanceof LegacyDecoratorAdapter))returned=LegacyInputValues.project(returned,(List<String>)BoundaryValues.read(getters));
            result.put("output",returned);
            result.put("invocation_completed", true);
        } catch (Throwable failure) {
            while (failure instanceof InvocationTargetException invocation && invocation.getCause() != null) failure = invocation.getCause();
            if (failure instanceof AdapterBindingFailure) result.put("failure_origin", "adapter_binding");
            if (failure instanceof BoundaryRuntime.Incomplete || failure instanceof ReflectiveOperationException || failure instanceof LinkageError) {
                result.put("status", "verification_incomplete"); result.put("issues", List.of(failure.toString()));
            } else {
                Map<String, Object> exception = new LinkedHashMap<>();
                exception.put("type", failure.getClass().getName());
                exception.put("message", String.valueOf(failure.getMessage()));
                List<Map<String, String>> causes = new ArrayList<>();
                Throwable cause = failure.getCause();
                while (cause != null && causes.size() < 8) {
                    causes.add(Map.of("type", cause.getClass().getName(), "message", String.valueOf(cause.getMessage())));
                    cause = cause.getCause();
                }
                if (!causes.isEmpty()) exception.put("causes", causes);
                if (cause != null) exception.put("cause_chain_truncated", true);
                result.put("exception", exception);
                result.put("invocation_completed", invoked);
            }
        }
        try {
            if (adapter instanceof LegacyBoundaryAdapter legacy) context.replaceState(legacy.snapshot(initial));
            if (adapter instanceof LegacyDecoratorAdapter decorator) context.replaceState(decorator.snapshot(initial));
            try { BoundaryRuntime.finish(); }
            catch (BoundaryRuntime.Incomplete incomplete) {
                result.put("status", "verification_incomplete");
                List<String> issues = new ArrayList<>((List<String>) result.getOrDefault("issues", List.of()));
                issues.add(incomplete.toString()); result.put("issues", issues);
            }
            result.put("context", context); result.put("writes", BoundaryRuntime.writes); result.put("removals", BoundaryRuntime.removals);
            result.put("external_calls", BoundaryRuntime.calls); result.put("probes", BoundaryRuntime.probes);
            if (input.containsKey("test_assets")) result.put("resource_events", il.co.dcd.verification.fixtures.FixtureResources.events());
            Path output = Path.of(args[1]), temporary = output.resolveSibling(output.getFileName() + ".tmp");
            try (var stream = Files.newOutputStream(temporary)) {
                var writer = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
                writer.writeStartDocument(); BoundaryValues.write(writer, "observation", result); writer.writeEndDocument(); writer.close();
            }
            Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING);
        } catch (Throwable incomplete) {
            throw new BoundaryRuntime.Incomplete("Observation could not be captured: " + incomplete);
        }
    }

    @SuppressWarnings("unchecked") private static void settings(Map<String, Object> setting) throws Exception {
        Class<?> type = LegacyBoundaryAdapter.load((String) setting.get("class"));
        List<Object> arguments = (List<Object>) setting.get("arguments");
        List<Method> matches = Arrays.stream(type.getMethods()).filter(method -> Modifier.isStatic(method.getModifiers())
            && method.getName().equals(setting.get("method")) && method.getParameterCount() == arguments.size()).toList();
        if (matches.size() != 1) throw new BoundaryRuntime.Incomplete("Settings method not uniquely bound");
        Object[] values = arguments.toArray();
        for (int index = 0; index < values.length; index++) if (values[index] != null && Set.class.isAssignableFrom(matches.get(0).getParameterTypes()[index])) {
            if (!(values[index] instanceof Collection<?> collection)) throw new BoundaryRuntime.Incomplete("Settings set argument needs an explicit adapter");
            values[index] = new LinkedHashSet<>(collection);
        }
        try { matches.get(0).invoke(null, values); }
        catch (IllegalArgumentException mismatch) { throw new BoundaryRuntime.Incomplete("Settings argument conversion needs an explicit adapter"); }
    }
}
