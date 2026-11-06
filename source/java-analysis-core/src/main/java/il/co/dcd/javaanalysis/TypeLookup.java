package il.co.dcd.javaanalysis;

import java.util.*;

/** Indexed source lookup boundary; implementations must cap ambiguous results at two. */
public interface TypeLookup {
    boolean contains(String fqcn);
    List<String> eligible(Set<String> names, String source);
    boolean existsOutsideVisibility(Set<String> names, String source);
}
