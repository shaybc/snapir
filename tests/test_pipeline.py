from pathlib import Path

from snapir.pipeline import ConversionPipeline


def _write_source(source: Path, with_extra: bool = False) -> None:
    source.mkdir(parents=True, exist_ok=True)
    (source / "flow.xml").write_text(
        """
        <root>
          <operation name="CreateOrder" />
          <component name="SharedCache" />
          <field name="order_id" javaType="string" />
          <field name="created_at" />
        </root>
        """.strip(),
        encoding="utf-8",
    )
    if with_extra:
        (source / "other.dse").write_text('<design><field name="quantity"/></design>', encoding="utf-8")


def test_pipeline_persists_only_accepted_version_and_reuses_by_component_hash(tmp_path: Path) -> None:
    source = tmp_path / "src"
    out = tmp_path / "out"
    _write_source(source)

    pipeline = ConversionPipeline(source, out, version="v1")
    first = pipeline.run()

    assert first.accepted is True
    assert first.reused is False
    assert (first.artifact_dir / "accepted.json").exists()
    assert (first.artifact_dir / "pom.xml").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "SharedComponentLibrary.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "SharedUtilities.java").exists()
    assert (first.artifact_dir / "src" / "test" / "java" / "com" / "snapir" / "generated" / "ConvertedComponentTest.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "CreateOrderController.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "CreateOrderService.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "CreateOrderContext.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "CreateOrderXmlMapper.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "ErrorMapper.java").exists()
    assert (first.artifact_dir / "src" / "main" / "java" / "com" / "snapir" / "generated" / "ApplicationBootstrap.java").exists()
    assert (first.artifact_dir / "artifact-metadata.json").exists()
    assert (first.artifact_dir / "maven_build.json").exists()
    assert (first.artifact_dir / "loop_history.json").exists()
    assert (first.artifact_dir / "final_accepted_implementation.java").exists()

    second = pipeline.run()
    assert second.accepted is True
    assert second.reused is True
    assert second.artifact_dir == first.artifact_dir


def test_pipeline_changes_component_hash_when_semantics_change(tmp_path: Path) -> None:
    source = tmp_path / "src"
    out = tmp_path / "out"
    _write_source(source)

    first = ConversionPipeline(source, out, version="v1").run()
    _write_source(source, with_extra=True)
    second = ConversionPipeline(source, out, version="v1").run()

    assert first.component_hash != second.component_hash
    assert first.artifact_dir != second.artifact_dir
