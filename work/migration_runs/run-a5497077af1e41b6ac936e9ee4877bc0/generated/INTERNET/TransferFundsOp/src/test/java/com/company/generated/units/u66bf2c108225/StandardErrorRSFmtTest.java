package com.company.generated.units.u66bf2c108225;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class StandardErrorRSFmtTest {

    @Test
    public void testFormatStandardErrorReply() throws Exception {
        ErrorReply reply = new ErrorReply("SYSTEM", "500", "Database connection failed", "req-12345");
        StandardErrorRSFmtMapper mapper = new StandardErrorRSFmtMapper();
        String xml = mapper.format(reply);

        assertNotNull(xml);
        assertTrue(xml.contains("<ErrorCategory>SYSTEM</ErrorCategory>"));
        assertTrue(xml.contains("<ErrorNumber>500</ErrorNumber>"));
        assertTrue(xml.contains("<ErrorDescription>Database connection failed</ErrorDescription>"));
        assertTrue(xml.contains("<RequestId>req-12345</RequestId>"));
    }

    @Test
    public void testUnformatStandardErrorReply() throws Exception {
        String xml = "<ErrorReply><ErrorCategory>AUTH</ErrorCategory><ErrorNumber>401</ErrorNumber><ErrorDescription>Unauthorized</ErrorDescription><RequestId>req-999</RequestId></ErrorReply>";
        StandardErrorRSFmtMapper mapper = new StandardErrorRSFmtMapper();
        ErrorReply reply = mapper.unformat(xml);

        assertNotNull(reply);
        assertEquals("AUTH", reply.getErrorCategory());
        assertEquals("401", reply.getErrorNumber());
        assertEquals("Unauthorized", reply.getErrorDescription());
        assertEquals("req-999", reply.getRequestId());
    }

    @Test
    public void testNilDecoratorFormat() throws Exception {
        ErrorReply reply = new ErrorReply(null, null, null, null);
        StandardErrorRSFmtMapper mapper = new StandardErrorRSFmtMapper();
        String xml = mapper.format(reply);

        assertNotNull(xml);
        assertTrue(xml.contains("xsi:nil=\"true\""));
    }

    @Test
    public void testNilDecoratorUnformat() throws Exception {
        String xml = "<ErrorReply xsi:nil=\"true\"/>";
        StandardErrorRSFmtMapper mapper = new StandardErrorRSFmtMapper();
        ErrorReply reply = mapper.unformat(xml);

        assertNull(reply);
    }
}
