package il.co.dcd.verification.harness;

import java.util.*;

/** Process-local controls and observable event recording, reset for every isolated JVM case. */
public final class BoundaryRuntime {
    public static final class Incomplete extends RuntimeException { public Incomplete(String message) { super(message); incomplete.add(message); } }
    public static final List<Map<String, Object>> writes = new ArrayList<>(), removals = new ArrayList<>(), calls = new ArrayList<>();
    public static final List<Map<String, String>> probes = new ArrayList<>();
    private static List<Map<String, Object>> replay = List.of();
    private static int cursor;
    private static long clock;
    private static Random random;
    private static final List<String> incomplete = new ArrayList<>();

    private BoundaryRuntime() { }

    @SuppressWarnings("unchecked")
    static void reset(Map<String, Object> controls) {
        clock = ((Number) controls.get("clock_millis")).longValue();
        random = new Random(((Number) controls.get("random_seed")).longValue());
        replay = (List<Map<String, Object>>) controls.get("external_responses"); cursor = 0;
        writes.clear(); removals.clear(); calls.clear(); probes.clear(); incomplete.clear();
        TimeZone.setDefault(TimeZone.getTimeZone("UTC")); Locale.setDefault(Locale.ROOT);
    }

    public static long now() { return clock; }
    public static long nextSeed() { return random.nextLong(); }
    public static double random() { return random.nextDouble(); }
    public static java.time.Clock fixedClock() { return java.time.Clock.fixed(java.time.Instant.ofEpochMilli(clock), java.time.ZoneOffset.UTC); }
    public static java.text.SimpleDateFormat dateFormat(java.text.SimpleDateFormat format) {
        java.util.Calendar start = new java.util.GregorianCalendar(TimeZone.getTimeZone("UTC"), Locale.ROOT);
        start.setTimeInMillis(clock); start.add(java.util.Calendar.YEAR, -80); format.set2DigitYearStart(start.getTime()); return format;
    }

    public static void hit(String identity, String outcome) {
        if (probes.size() >= 100000) throw new Incomplete("Boundary probe limit exceeded");
        probes.add(Map.of("id", identity, "outcome", outcome));
    }
    public static boolean condition(String identity, boolean value) { hit(identity, Boolean.toString(value)); return value; }
    public static <T> T value(String identity, T value) { hit(identity, "evaluated"); return value; }
    public static <T> Iterable<T> iteration(String id, Iterable<T> values) {
        return () -> {
            Iterator<T> original = values.iterator();
            return new Iterator<>() {
                public boolean hasNext() { return condition(id, original.hasNext()); }
                public T next() { return original.next(); }
                public void remove() { original.remove(); }
            };
        };
    }
    @SuppressWarnings("unchecked") private static <T> Iterable<T> arrayIteration(String id, Object array) {
        Objects.requireNonNull(array);
        return () -> new Iterator<>() {
            int index;
            public boolean hasNext() { return condition(id, index < java.lang.reflect.Array.getLength(array)); }
            public T next() { return (T) java.lang.reflect.Array.get(array, index++); }
        };
    }
    public static <T> Iterable<T> iteration(String id, T[] values) { return arrayIteration(id, values); }
    public static Iterable<Integer> iteration(String id, int[] values) { return arrayIteration(id, values); }
    public static Iterable<Long> iteration(String id, long[] values) { return arrayIteration(id, values); }
    public static Iterable<Boolean> iteration(String id, boolean[] values) { return arrayIteration(id, values); }
    public static Iterable<Character> iteration(String id, char[] values) { return arrayIteration(id, values); }
    public static Iterable<Byte> iteration(String id, byte[] values) { return arrayIteration(id, values); }
    public static Iterable<Short> iteration(String id, short[] values) { return arrayIteration(id, values); }
    public static Iterable<Float> iteration(String id, float[] values) { return arrayIteration(id, values); }
    public static Iterable<Double> iteration(String id, double[] values) { return arrayIteration(id, values); }
    public static void written(String key, Object value) { writes.add(event(key, value)); }
    public static void removed(String key, Object value) { removals.add(event(key, value)); }
    private static Map<String, Object> event(String key, Object value) {
        Map<String, Object> event = new LinkedHashMap<>(); event.put("key", key); event.put("value", BoundaryValues.snapshot(value)); return event;
    }

    public static Object external(Object receiver, String target, Object[] arguments) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("target", target); event.put("arguments", Arrays.stream(arguments).map(BoundaryValues::snapshot).toList());
        if (receiver instanceof java.util.logging.Logger logger) event.put("receiver", logger.getName());
        calls.add(event);
        if (target.startsWith("logging:")) return null;
        if (cursor >= replay.size()) throw new Incomplete("Missing external replay response for " + target);
        Map<String, Object> response = replay.get(cursor++);
        if (!target.equals(response.get("target")) || !BoundaryValues.comparable(event.get("arguments")).equals(BoundaryValues.comparable(response.get("arguments"))))
            throw new Incomplete("External replay target/arguments differ at call " + cursor);
        if (response.containsKey("exception_type")) {
            try {
                Object exception = Class.forName((String) response.get("exception_type")).getConstructor(String.class)
                    .newInstance(response.getOrDefault("message", ""));
                return BoundaryRuntime.<RuntimeException, Object>raise((Throwable) exception);
            } catch (ReflectiveOperationException exception) { throw new Incomplete("Unsupported replay exception type"); }
        }
        return response.get("value");
    }
    public static Object external(Object receiver, String target, Object[] arguments, String expectedType) {
        Object value = external(receiver, target, arguments);
        if (expectedType.equals("void")) {
            if (value != null) throw new Incomplete("Void replay response must not contain a result");
            return null;
        }
        try {
            if (value instanceof Number number) {
                java.math.BigDecimal numeric = new java.math.BigDecimal(number.toString());
                value = switch (expectedType) {
                    case "int", "java.lang.Integer" -> numeric.intValueExact();
                    case "long", "java.lang.Long" -> numeric.longValueExact();
                    case "short", "java.lang.Short" -> numeric.shortValueExact();
                    case "byte", "java.lang.Byte" -> numeric.byteValueExact();
                    case "float", "java.lang.Float" -> numeric.floatValue();
                    case "double", "java.lang.Double" -> numeric.doubleValue();
                    default -> value;
                };
            }
            if ((expectedType.equals("char") || expectedType.equals("java.lang.Character")) && value instanceof String text && text.length() == 1) value = text.charAt(0);
            String boxed = Map.of("int", "java.lang.Integer", "long", "java.lang.Long", "short", "java.lang.Short", "byte", "java.lang.Byte",
                "float", "java.lang.Float", "double", "java.lang.Double", "char", "java.lang.Character", "boolean", "java.lang.Boolean").getOrDefault(expectedType, expectedType);
            if (value == null && !boxed.equals(expectedType) || value != null && !Class.forName(boxed).isInstance(value))
                throw new Incomplete("Replay value does not implement declared return type " + expectedType);
            return value;
        } catch (ArithmeticException | ClassNotFoundException error) { throw new Incomplete("Replay value cannot be represented as " + expectedType); }
    }
    @SuppressWarnings("unchecked") private static <T extends Throwable, R> R raise(Throwable value) throws T { throw (T) value; }
    static void finish() {
        if (!incomplete.isEmpty()) throw new Incomplete("Uncontrolled execution was caught by legacy/native code: " + incomplete.get(0));
        if (cursor != replay.size()) throw new Incomplete("Unused external replay responses: " + (replay.size() - cursor));
    }

    /** Native adapters expose real writes/removals through this map, not a guessed post-hoc diff. */
    public static final class ContextMap extends LinkedHashMap<String, Object> {
        public ContextMap(Map<String, Object> initial) { super(initial); }
        public Object put(String key, Object value) { Object old = super.put(key, value); written(key, value); return old; }
        public Object remove(Object key) { Object old = super.remove(key); BoundaryRuntime.removed((String) key, old); return old; }
        public void putAll(Map<? extends String, ?> values) { values.forEach(this::put); }
        public void clear() { for (String key : new ArrayList<>(keySet())) remove(key); }
        public Object putIfAbsent(String key, Object value) { Object old = get(key); if (old == null) put(key, value); return old; }
        public boolean remove(Object key, Object value) { if (containsKey(key) && Objects.equals(get(key), value)) { remove(key); return true; } return false; }
        public Object replace(String key, Object value) { return containsKey(key) ? put(key, value) : null; }
        public boolean replace(String key, Object old, Object value) { if (containsKey(key) && Objects.equals(get(key), old)) { put(key, value); return true; } return false; }
        public void replaceAll(java.util.function.BiFunction<? super String, ? super Object, ?> function) { for (String key : new ArrayList<>(keySet())) put(key, function.apply(key, get(key))); }
        public Object compute(String key, java.util.function.BiFunction<? super String, ? super Object, ?> function) {
            Object value = function.apply(key, get(key)); if (value == null) { if (containsKey(key)) remove(key); } else put(key, value); return value;
        }
        public Object computeIfAbsent(String key, java.util.function.Function<? super String, ?> function) { return get(key) == null ? compute(key, (k, old) -> function.apply(k)) : get(key); }
        public Object computeIfPresent(String key, java.util.function.BiFunction<? super String, ? super Object, ?> function) { return get(key) == null ? null : compute(key, function); }
        public Object merge(String key, Object value, java.util.function.BiFunction<? super Object, ? super Object, ?> function) { return compute(key, (k, old) -> old == null ? value : function.apply(old, value)); }
        public Set<Map.Entry<String, Object>> entrySet() {
            Set<Map.Entry<String, Object>> original = super.entrySet();
            return new AbstractSet<>() {
                public int size() { return original.size(); }
                public Iterator<Map.Entry<String, Object>> iterator() {
                    var iterator = original.iterator();
                    return new Iterator<>() {
                        Map.Entry<String, Object> current;
                        public boolean hasNext() { return iterator.hasNext(); }
                        public Map.Entry<String, Object> next() {
                            current = iterator.next(); var entry = current;
                            return new Map.Entry<>() {
                                public String getKey() { return entry.getKey(); }
                                public Object getValue() { return entry.getValue(); }
                                public Object setValue(Object value) { Object old = entry.setValue(value); written(entry.getKey(), value); return old; }
                                public boolean equals(Object other) { return entry.equals(other); }
                                public int hashCode() { return entry.hashCode(); }
                            };
                        }
                        public void remove() { String key = current.getKey(); Object value = current.getValue(); iterator.remove(); BoundaryRuntime.removed(key, value); }
                    };
                }
            };
        }
        private Map<String, Object> view() { return new AbstractMap<>() { public Set<Map.Entry<String, Object>> entrySet() { return ContextMap.this.entrySet(); } }; }
        public Set<String> keySet() { return view().keySet(); }
        public Collection<Object> values() { return view().values(); }
        public void replaceState(Map<String, Object> state) { super.clear(); super.putAll(state); }
    }
}
