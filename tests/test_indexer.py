from pathlib import Path
import json

from snapir.indexer import ComposerIndexer


def test_build_and_persist_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.xml").write_text(
        """
        <root>
          <operation name=\"CreateOrder\" type=\"sync\"/>
          <component name=\"CustomerLookup\" language=\"java\"/>
        </root>
        """.strip(),
        encoding="utf-8",
    )
    (source / "b.dse").write_text(
        """
        <design>
          <sharedComponent id=\"SharedCache\" kind=\"redis\"/>
          <format name=\"OrderFormat\"/>
        </design>
        """.strip(),
        encoding="utf-8",
    )

    idx = ComposerIndexer(source, version="v1")
    payload1 = idx.build()
    payload2 = idx.build()
    assert payload1 == payload2

    out = tmp_path / "out"
    artifact_dir = idx.persist(out)

    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "v1"

    operations = json.loads((artifact_dir / "operations_catalog.json").read_text(encoding="utf-8"))
    assert "CreateOrder" in operations

    components = json.loads((artifact_dir / "component_catalog.json").read_text(encoding="utf-8"))
    assert set(components) == {"CustomerLookup", "SharedCache"}
