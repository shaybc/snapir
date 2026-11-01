package il.co.dcd.verification.harness;

import java.util.Map;
import org.w3c.dom.Element;

/** Explicit native boundary/API bridge; observations are captured by the harness, never fabricated. */
public interface BoundaryAdapter {
    Object invoke(String xml, Map<String, Object> context, Element configuration) throws Exception;
}
