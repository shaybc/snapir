package il.co.dcd.verification;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.*;
import java.util.*;

/** Controlled time/random and replay; only format comparisons opt out of unknown-library rejection. */
final class HarnessCalls {
    private final Map<String, String> bindings;
    private final Set<String> issues;
    private final java.util.function.Predicate<Node> included;
    private final boolean fixtureResources;
    private final boolean allowUnknownCalls;
    HarnessCalls(Map<String, String> bindings, Set<String> issues, java.util.function.Predicate<Node> included) {
        this(bindings,issues,included,false);
    }
    HarnessCalls(Map<String, String> bindings, Set<String> issues, java.util.function.Predicate<Node> included, boolean fixtureResources) {
        this(bindings,issues,included,fixtureResources,false);
    }
    HarnessCalls(Map<String, String> bindings, Set<String> issues, java.util.function.Predicate<Node> included, boolean fixtureResources, boolean allowUnknownCalls) {
        this.bindings = bindings; this.issues = issues; this.included = included; this.fixtureResources = fixtureResources; this.allowUnknownCalls = allowUnknownCalls;
    }

    void scan(Node unit) {
        for (MethodReferenceExpr reference : unit.findAll(MethodReferenceExpr.class)) {
            if (!included.test(reference)) continue;
            try {
                var method = reference.resolve(); String owner = method.declaringType().getQualifiedName();
                if (owner.equals("java.lang.System") && method.getName().equals("currentTimeMillis"))
                    reference.replace(StaticJavaParser.parseExpression("() -> " + HarnessProbes.RUNTIME + ".now()"));
                else if (owner.equals("java.lang.Math") && method.getName().equals("random"))
                    reference.replace(StaticJavaParser.parseExpression("() -> " + HarnessProbes.RUNTIME + ".random()"));
                else if (bindings.containsKey(method.getQualifiedSignature()) || !allowUnknownCalls && method.toAst().isEmpty() && !safe(owner))
                    unsupported("Method reference requires an explicit adapter: " + reference);
            } catch (RuntimeException exception) { issues.add("Unresolved harness method reference: " + reference); }
        }
        var calls = new ArrayList<>(unit.findAll(MethodCallExpr.class)); Collections.reverse(calls);
        for (MethodCallExpr call : calls) {
            if (!included.test(call)) continue;
            if (call.getScope().map(Object::toString).orElse("").equals(HarnessProbes.RUNTIME)) continue;
            try {
                var method = call.resolve();
                String owner = method.declaringType().getQualifiedName(), name = method.getName(), target = method.getQualifiedSignature();
                if (owner.startsWith("il.co.dcd.verification.harness.")) continue;
                if (fixtureResources && Set.of("java.sql.Connection", "java.sql.PreparedStatement", "java.sql.CallableStatement", "java.sql.Statement", "java.sql.ResultSet").contains(owner)
                        && !method.isStatic() && call.getScope().isPresent()) {
                    Expression checked = StaticJavaParser.parseExpression("il.co.dcd.verification.fixtures.FixtureResources.checked(null)");
                    checked.asMethodCallExpr().setArgument(0,call.getScope().orElseThrow().clone()); call.setScope(checked); continue;
                }
                if (bindings.containsKey(target) || owner.startsWith("java.util.logging.") && Set.of("log", "warning", "info", "severe", "fine").contains(name)) {
                    String canonical = bindings.getOrDefault(target, "logging:" + target);
                    Expression receiver = method.isStatic() ? new NullLiteralExpr() : call.getScope().map(Expression::clone).orElse(new ThisExpr());
                    var arguments = new ArrayInitializerExpr(new com.github.javaparser.ast.NodeList<>(call.getArguments().stream().map(Expression::clone).toList()));
                    var array = new ArrayCreationExpr().setElementType("Object").setLevels(new com.github.javaparser.ast.NodeList<>(new com.github.javaparser.ast.ArrayCreationLevel())).setInitializer(arguments);
                    String returns = method.getReturnType().isVoid() ? "void" : call.calculateResolvedType().erasure().describe();
                    Expression replacement = HarnessProbes.call("external", receiver, new StringLiteralExpr(canonical), array, new StringLiteralExpr(returns));
                    if (!method.getReturnType().isVoid()) replacement = new CastExpr(StaticJavaParser.parseType(returns), replacement);
                    call.replace(replacement);
                } else if (owner.equals("java.lang.System") && name.equals("currentTimeMillis")) call.replace(HarnessProbes.call("now"));
                else if (owner.equals("java.lang.Math") && name.equals("random")) call.replace(HarnessProbes.call("random"));
                else if (owner.startsWith("java.time.")
                        && name.equals("now") && call.getArguments().isEmpty()) call.addArgument(HarnessProbes.call("fixedClock"));
                else if (owner.equals("java.time.Clock") && Set.of("systemUTC", "systemDefaultZone").contains(name)) call.replace(HarnessProbes.call("fixedClock"));
                else if (owner.equals("java.lang.System") && !name.equals("arraycopy")) unsupported(target);
                else if (owner.equals("java.lang.Class") && Set.of("forName", "newInstance", "getClassLoader").contains(name)) unsupported(target);
                else if (owner.equals("java.util.Calendar") && name.equals("getInstance")) unsupported(target);
                else if (!allowUnknownCalls && method.toAst().isEmpty() && !safe(owner) && !NativeCodecPolicy.method(owner, name, call)) unsupported(target);
            } catch (RuntimeException exception) {
                issues.add("Unresolved harness call: " + call + " (" + exception.getClass().getSimpleName() + ")");
            }
        }
        for (ObjectCreationExpr creation : new ArrayList<>(unit.findAll(ObjectCreationExpr.class))) {
            if (!included.test(creation)) continue;
            try {
                var constructor = creation.resolve();
                String owner = constructor.declaringType().getQualifiedName();
                if (owner.equals("java.util.Date") && creation.getArguments().isEmpty()) creation.addArgument(HarnessProbes.call("now"));
                else if (owner.equals("java.util.Random") && creation.getArguments().isEmpty()) creation.addArgument(HarnessProbes.call("nextSeed"));
                else if (owner.equals("java.text.SimpleDateFormat")) creation.replace(HarnessProbes.call("dateFormat", creation.clone()));
                else if (!allowUnknownCalls && constructor.toAst().isEmpty() && constructor.declaringType().toAst().isEmpty() && !safe(owner)
                    && !NativeCodecPolicy.constructor(owner, creation.getArguments().size())) unsupported(constructor.getQualifiedSignature());
            } catch (RuntimeException exception) { issues.add("Unresolved harness construction: " + creation); }
        }
    }

    private void unsupported(String target) { issues.add("Uncontrolled external dependency: " + target); }
    private static boolean safe(String owner) {
        if (owner.startsWith("java.lang.reflect.") || owner.startsWith("java.lang.invoke.") || owner.equals("java.lang.Thread")
                || owner.equals("java.lang.Runtime") || owner.equals("java.lang.ProcessBuilder") || owner.equals("java.util.UUID")
                || owner.equals("java.lang.ClassLoader") || owner.equals("java.util.SplittableRandom") || owner.equals("java.util.GregorianCalendar")
                || owner.startsWith("java.util.random.") || owner.startsWith("java.util.zip.") || owner.equals("java.util.Scanner")
                || owner.startsWith("java.util.concurrent.") || owner.startsWith("java.util.Timer") || owner.startsWith("java.util.ServiceLoader")) return false;
        return owner.startsWith("java.lang.") || owner.startsWith("java.util.") || owner.startsWith("java.math.")
            || owner.startsWith("java.text.") || owner.startsWith("java.time.") || owner.startsWith("java.util.logging.")
            || owner.startsWith("javax.xml.") || owner.startsWith("org.w3c.dom.") || owner.startsWith("org.xml.sax.")
            || Set.of("java.io.StringReader", "java.io.StringWriter", "java.io.ByteArrayInputStream", "java.io.ByteArrayOutputStream",
                "java.io.IOException", "java.io.Reader", "java.io.Writer").contains(owner)
            || owner.startsWith("il.co.dcd.verification.harness.");
    }
}
