"""Render the project README as local HTML for a new browser tab."""

from html import escape
from pathlib import Path
import tempfile
from urllib.parse import urljoin
import webbrowser


def render_readme(readme: Path) -> str:
    """Render Markdown with tables/code and resolve local links against its folder."""
    import mistune

    base_url = readme.resolve().parent.as_uri() + "/"

    class LocalLinkRenderer(mistune.HTMLRenderer):
        """Keep relative document and image links usable from temporary HTML."""

        def link(self, text, url, title=None):
            """Resolve document links while retaining page-local fragments."""
            return super().link(text, url if url.startswith("#") else urljoin(base_url, url), title)

        def image(self, text, url, title=None):
            """Resolve image locations against the README directory."""
            return super().image(text, urljoin(base_url, url), title)

    markdown = mistune.create_markdown(
        renderer=LocalLinkRenderer(escape=True, allow_harmful_protocols=("file:",)), plugins=["table"]
    )
    body = markdown(readme.read_text(encoding="utf-8"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(readme.name)} — Snapir</title>
<style>
body {{ max-width: 1000px; margin: 40px auto; padding: 0 24px; font: 16px/1.6 system-ui, sans-serif; color: #222; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
th, pre {{ background: #f5f5f5; }}
pre {{ padding: 16px; overflow-x: auto; }}
code {{ font-family: monospace; }}
img {{ max-width: 100%; }}
</style></head><body>{body}</body></html>"""


def open_readme() -> Path:
    """Write temporary HTML and request a browser tab; raise on launch failure."""
    readme = Path(__file__).resolve().parent.parent / "README.md"
    content = render_readme(readme)
    # Keep the file after process exit so the browser can read it asynchronously.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html",
                                     prefix="snapir-readme-", delete=False) as output:
        output.write(content)
        path = Path(output.name)
    try:
        opened = webbrowser.open(path.as_uri(), new=2)
    except webbrowser.Error as exc:
        raise RuntimeError(f"Could not open README in a browser. Rendered file: {path}") from exc
    if not opened:
        raise RuntimeError(f"Could not open README in a browser. Rendered file: {path}")
    print(f"README opened in browser: {path}")
    return path
