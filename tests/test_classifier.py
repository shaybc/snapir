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
          <mysteryNode field='mysteryValue'/>
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


def test_tag_semantic_resolver_queue_and_dictionary(tmp_path: Path) -> None:
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'flow.xml').write_text(
        """
        <root>
          <context_read field='alpha'/>
          <unknownTag field='beta'/>
        </root>
        """.strip(),
        encoding='utf-8',
    )

    payload = DataflowClassifier(source, version='v1').build()
    semantics = payload['normalized_tag_semantics']
    queue = payload['llm_tag_interpretation_queue']

    assert semantics['context_read']['semantic'] == 'read'
    assert semantics['unknowntag']['requires_llm'] is True
    assert any(entry['normalized'] == 'unknowntag' for entry in queue)
    unknown = next(entry for entry in queue if entry['normalized'] == 'unknowntag')
    assert unknown['llm_contract']['retry_on_schema_invalid'] is True
    assert unknown['llm_contract']['response_schema']['required'] == [
        'normalized_tag', 'semantic', 'confidence', 'rationale', 'provenance'
    ]


def test_unknown_tag_accepts_valid_llm_resolution_with_replayability(tmp_path: Path) -> None:
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'flow.xml').write_text("<root><unknownTag field='beta'/></root>", encoding='utf-8')

    classifier = DataflowClassifier(source, version='v1')
    classifier.build()
    ok, reason = classifier.tag_resolver.resolve_unknown_with_llm(
        {
            'normalized_tag': 'unknowntag',
            'semantic': 'read',
            'confidence': 0.87,
            'rationale': 'Used as a source-like operation in XML.',
            'provenance': {
                'model': 'gpt-x',
                'prompt_template': 'tag-resolution-v1',
                'response_schema_version': '1.0',
            },
        }
    )
    assert ok is True
    assert reason == 'accepted'
    accepted = classifier.tag_resolver.accepted_semantics['unknowntag']
    assert accepted['semantic'] == 'read'
    assert accepted['confidence'] == 0.87
    assert 'replayability' in accepted


def test_unknown_tag_rejects_invalid_schema_response(tmp_path: Path) -> None:
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'flow.xml').write_text("<root><unknownTag field='beta'/></root>", encoding='utf-8')

    classifier = DataflowClassifier(source, version='v1')
    classifier.build()
    ok, reason = classifier.tag_resolver.resolve_unknown_with_llm(
        {
            'normalized_tag': 'unknowntag',
            'semantic': 'read',
            'confidence': 1.5,
            'rationale': 'bad confidence',
            'provenance': {
                'model': 'gpt-x',
                'prompt_template': 'tag-resolution-v1',
                'response_schema_version': '1.0',
            },
        },
        retry_count=2,
    )
    assert ok is False
    assert reason.startswith('schema_invalid_rejected:')
