package il.co.dcd.fixtures.protocol;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ProtocolTest {
    @Test void strictUrlsDoNotInterceptVendorSchemes() {
        FixtureUrl u=FixtureUrl.parse("jdbc:fixtures://127.0.0.1:15432/scenario?resource=database&execution=run");
        assertTrue(u.local());assertEquals(15432,u.endpoint().getPort());assertEquals("database",u.resource());
        for(String bad : List.of("jdbc:oracle:thin:@host","jdbc:fixtures://host/s","jdbc:fixtures://user:secret@host:1/s",
            "jdbc:fixtures://host:1/a/b","jdbc:fixtures://host:1/s?resource=a&resource=b","jdbc:fixtures://host:1/%2F","jdbc:fixtures://host:1/s?x=y"))
            assertThrows(IllegalArgumentException.class,()->FixtureUrl.parse(bad));
    }
    @Test void typedWireValuesAndCanonicalUnicode() throws Exception {
        Object value=Map.of("amount",new BigDecimal("1234567890.0100"),"date",java.sql.Date.valueOf("2024-01-02"),"xml","\ufeff<x>\r\nשלום 😀</x>");
        assertEquals(value,Values.decode(Json.read(Json.bytes(Values.encode(value)))));
        assertEquals("{\"a\":null,\"z\":\"\\u05e9\\ud83d\\ude00\\r\\n\"}",Json.canonical(new TreeMap<>(){{put("a",null);put("z","ש😀\r\n");}}));
        assertThrows(Exception.class,()->Json.read("{\"x\":1,\"x\":2}".getBytes()));
    }
}
