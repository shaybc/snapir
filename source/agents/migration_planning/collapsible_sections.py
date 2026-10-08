"""Render escaped report evidence inside optional Markdown HTML disclosures."""

from html import escape


def collapsible_section(title, lines):
    """Keep the title visible and expose the full evidence when expanded."""
    content = "\n".join("<li>" + escape(line.strip().removeprefix("- ")) + "</li>" for line in lines)
    return "\n<details>\n<summary>" + escape(title) + "</summary>\n<ul>\n" + content + "\n</ul>\n</details>\n"
