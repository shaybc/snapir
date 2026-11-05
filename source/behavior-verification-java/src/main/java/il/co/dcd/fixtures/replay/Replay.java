package il.co.dcd.fixtures.replay;

import java.math.BigDecimal;
import java.util.*;

/** Dependency-free exact-SQL/value semantics shared by local and network fixtures. */
public final class Replay {
    private Replay() { }
    public static boolean same(List<?> left, List<?> right) {
        if (left.size()!=right.size()) return false;
        for (int i=0;i<left.size();i++) {
            Object a=left.get(i),b=right.get(i);
            if (a instanceof Number && b instanceof Number) {
                if (new BigDecimal(a.toString()).compareTo(new BigDecimal(b.toString()))!=0) return false;
            } else if (!Objects.equals(a,b)) return false;
        }
        return true;
    }
    public static Map<String,Object> find(List<Map<String,Object>> queries,String sql,List<?> parameters) {
        for (Map<String,Object> query : queries)
            if (sql.equals(query.get("sql")) && same(parameters,(List<?>)query.get("parameters"))) return query;
        return null;
    }
    public static Object column(Object value,String getter) {
        return switch (getter) {
            case "getString" -> value==null ? null : String.valueOf(value);
            case "getInt" -> value==null ? 0 : new BigDecimal(value.toString()).intValueExact();
            case "getLong" -> value==null ? 0L : new BigDecimal(value.toString()).longValueExact();
            case "getBoolean" -> value==null ? false : (Boolean)value;
            case "getBigDecimal" -> value==null ? null : new BigDecimal(value.toString());
            default -> value;
        };
    }
}
