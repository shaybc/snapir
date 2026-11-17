package com.snapir.validator;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;

/** Machine-readable findings; no application code is loaded or executed. */
final class Report {
    final JsonNode policy;
    final List<Map<String,Object>> findings = new ArrayList<>();
    Report(JsonNode policy) { this.policy = policy; }
    boolean matches(String key, String reference) {
        for (JsonNode value : policy.path(key)) {
            String prefix = value.asText();
            if (reference.equals(prefix) || reference.startsWith(prefix + ".")) return true;
        }
        return false;
    }
    boolean allowed(String key, String value) {
        for (JsonNode entry : policy.path(key)) if (entry.asText().equals(value)) return true;
        return false;
    }
    void add(String rule, String file, int line, String reference, String message, String fix) {
        var finding = new LinkedHashMap<String,Object>();
        finding.put("rule",rule); finding.put("severity","error"); finding.put("file",file);
        finding.put("line",line); finding.put("reference",reference);
        finding.put("message",message); finding.put("suggested_fix",fix);
        if (!findings.contains(finding)) findings.add(finding);
    }
}
