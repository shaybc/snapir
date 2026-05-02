from pathlib import Path
import json

from snapir.classifier import DataflowClassifier


def test_classifier_assigns_fields_and_persists_traces(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "flow.xml").write_text(
        """
        <root>
          <format name='OrderFmt'>
            <field name='customerId'/>
            <field name='resultCode'/>
            <field name='errorCode'/>
          </format>
          <contextRead field='customerId'/>
          <contextWrite field='resultCode'/>
          <contextRead field='sessionKey'/>
          <contextWrite field='sessionKey'/>
        </root>
        """.strip(),
        encoding="utf-8",
    )

    classifier = DataflowClassifier(source, version="v1")
    payload = classifier.build()

    assert payload["field_classification"]["customerId"] == "INPUT"
    assert payload["field_classification"]["resultCode"] == "OUTPUT"
    assert payload["field_classification"]["sessionKey"] == "INTERMEDIATE"
    assert payload["field_classification"]["errorCode"] == "ERROR"

    out_dir = classifier.persist(tmp_path / "out")
    assignments = json.loads((out_dir / "field_classification.json").read_text(encoding="utf-8"))
    traces = json.loads((out_dir / "classification_traces.json").read_text(encoding="utf-8"))

    assert assignments == payload["field_classification"]
    assert any(t["field"] == "customerId" and t["rule"] == "read_without_write" for t in traces)
    assert any(t["field"] == "errorCode" and t["rule"] == "tag_semantic_error_name" for t in traces)
