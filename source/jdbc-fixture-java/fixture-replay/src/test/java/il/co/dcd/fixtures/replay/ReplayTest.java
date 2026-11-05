package il.co.dcd.fixtures.replay;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ReplayTest {
    @Test void existingValueEqualityAndTypedGettersRemainExact() {
        assertTrue(Replay.same(List.of(1,"X"),List.of(new BigDecimal("1.00"),"X")));
        assertFalse(Replay.same(List.of("1"),List.of(1)));
        assertFalse(Replay.same(List.of("x"),List.of("X")));
        assertTrue(Replay.same(Arrays.asList((Object)null),Arrays.asList((Object)null)));
        assertEquals(0,Replay.column(null,"getInt"));
        assertThrows(ArithmeticException.class,()->Replay.column("1.2","getInt"));
        Map<String,Object> q=Map.of("sql","SELECT X","parameters",List.of(1));
        assertSame(q,Replay.find(List.of(q),"SELECT X",List.of(1L)));
        assertNull(Replay.find(List.of(q),"select X",List.of(1)));
    }
}
