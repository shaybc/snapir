from __future__ import annotations

from pathlib import Path

from tools.conversion_tools.decorator_chain_resolver_tool import (
    get_decorator_chain_for_field,
    resolve_decorator_chains,
)


def test_resolve_decorator_chains_returns_forward_order(tmp_path: Path):
    note = tmp_path / "FormatA.md"
    note.write_text(
        """
## Structure
<CCXML dataName="GetClientLinks">
  <CCString dataName="ClientId"/>
  decorator: <nilDecorator/>
  <CCDate dataName="RequestDate"/>
  decorator: <RemoveLeadingZerosDecorator/>
  decorator: <CCPadding padChar="0" length="9"/>
</CCXML>
""",
        encoding="utf-8",
    )

    chains = resolve_decorator_chains(str(note))

    assert chains == [
        ("ClientId/CCString", ["nilDecorator"]),
        ("RequestDate/CCDate", ["RemoveLeadingZerosDecorator", "CCPadding"]),
    ]
    assert get_decorator_chain_for_field(chains, "ClientId") == ["nilDecorator"]
    assert get_decorator_chain_for_field(chains, "Missing") == []


def test_ccxml_without_decorators_returns_no_chain(tmp_path: Path):
    note = tmp_path / "FormatA.md"
    note.write_text(
        """
## Structure
<CCXML dataName="GetClientLinks">
</CCXML>
""",
        encoding="utf-8",
    )

    assert resolve_decorator_chains(str(note)) == []
