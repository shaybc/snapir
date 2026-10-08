from __future__ import annotations

from pathlib import Path

from tools.java_analysis_tools.java_slicer import (
    extract_execute_method,
    extract_ibm_imports,
    extract_method,
)
from tools.java_analysis_tools.java_source_reader import resolve_source_path
from tools.java_analysis_tools.java_structural_summariser import (
    detect_context_access_patterns,
    summarise_java_class,
)


SAMPLE_JAVA = """
package com.bank.ops;

import java.util.Map;
import com.ibm.websphere.sca.Service;
import com.company.NativeThing;

public class GetClientLinksSP extends BaseStep implements Step {
    public void setClientId(String clientId) {
        this.clientId = clientId;
    }

    public int execute(Context context) {
        context.setValueAt("ClientId", clientId);
        String linkId = context.getValue("LinkId");
        if (linkId == null) {
            return 4;
        }
        return 0;
    }

    private String helper() {
        return "ok";
    }
}
"""


def test_extract_method_finds_named_method():
    method = extract_method(SAMPLE_JAVA, "execute")

    assert method is not None
    assert method.startswith("public int execute")
    assert 'context.setValueAt("ClientId", clientId);' in method
    assert "private String helper" not in method


def test_extract_execute_method_uses_execute_name():
    method = extract_execute_method(SAMPLE_JAVA)

    assert method is not None
    assert "return 0;" in method


def test_extract_ibm_imports_returns_only_com_ibm_lines():
    assert extract_ibm_imports(SAMPLE_JAVA) == ["com.ibm.websphere.sca.Service"]


def test_detect_context_access_patterns_extracts_field_names():
    assert detect_context_access_patterns(SAMPLE_JAVA) == ["ClientId", "LinkId"]


def test_resolve_source_path_maps_fqcn_to_correct_path_structure(tmp_path: Path):
    source_path = tmp_path / "com" / "bank" / "ops" / "GetClientLinksSP.java"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(SAMPLE_JAVA, encoding="utf-8")

    assert resolve_source_path(str(tmp_path), "com.bank.ops.GetClientLinksSP") == str(source_path)


def test_summarise_java_class_extracts_structural_facts():
    summary = summarise_java_class(
        SAMPLE_JAVA,
        parent_class="BaseStep",
        interfaces=["Step"],
    )

    assert summary.class_name == "GetClientLinksSP"
    assert summary.package == "com.bank.ops"
    assert summary.fqcn == "com.bank.ops.GetClientLinksSP"
    assert summary.parent_class == "BaseStep"
    assert summary.interfaces == ["Step"]
    assert summary.methods == ["setClientId", "execute", "helper"]
    assert summary.setters == ["setClientId"]
    assert summary.ibm_imports == ["com.ibm.websphere.sca.Service"]
    assert summary.return_codes["4"] == []
    assert summary.return_codes["0"] == []
    assert summary.context_fields_written == ["ClientId"]
    assert summary.context_fields_read == ["LinkId"]
    assert "context_access" in summary.behavior_types
    assert summary.source_char_count == len(SAMPLE_JAVA)
