package com.company.generated.units.u66bf2c108225;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class StandardErrorRSFmtBusinessTest {
    private final StandardErrorRSFmtMapper mapper = new StandardErrorRSFmtMapper();

    @Test
    public void formatsFullyPopulatedErrorReply() throws Exception {
        StandardErrorRSFmtMapper.ErrorReply reply = new StandardErrorRSFmtMapper.ErrorReply("CAT1", "500", "System Error", "REQ-123");
        String xml = mapper.format(reply);
        assertTrue(xml.contains("<ErrorCategory>CAT1</ErrorCategory>"));
        assertTrue(xml.contains("<ErrorNumber>500</ErrorNumber>"));
        assertTrue(xml.contains("<ErrorDescription>System Error</ErrorDescription>"));
        assertTrue(xml.contains("<RequestId>REQ-123</RequestId>"));

        StandardErrorRSFmtMapper.ErrorReply unformatted = mapper.unformat(xml);
        assertEquals("CAT1", unformatted.errorCategory());
        assertEquals("500", unformatted.errorNumber());
        assertEquals("System Error", unformatted.errorDescription());
        assertEquals("REQ-123", unformatted.requestId());
    }

    @Test
    public void handlesNullRequestIdWithNilDecorator() throws Exception {
        StandardErrorRSFmtMapper.ErrorReply reply = new StandardErrorRSFmtMapper.ErrorReply("CAT2", "404", "Not Found", null);
        String xml = mapper.format(reply);
        assertTrue(xml.contains("nil=\"true\"") || xml.contains("xsi:nil=\"true\""));

        StandardErrorRSFmtMapper.ErrorReply unformatted = mapper.unformat(xml);
        assertNull(unformatted.requestId());
        assertEquals("CAT2", unformatted.errorCategory());
        assertEquals("404", unformatted.errorNumber());
        assertEquals("Not Found", unformatted.errorDescription());
    }
}
