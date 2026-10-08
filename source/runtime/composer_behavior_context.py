"""Select documented replacement behavior and retain its source evidence."""

import hashlib
import json
import re
from pathlib import Path
from runtime.composer_conversion_knowledge import COMPOSER_BEHAVIOR_SECTIONS

COMPOSER_SECTIONS = tuple(heading for heading, _ in COMPOSER_BEHAVIOR_SECTIONS)


def required_composer_behavior():
    """Return embedded behavior without relying on a documentation file."""
    return [dict(document="embedded:composer_conversion_knowledge", heading=heading, content=content,
                 content_hash=hashlib.sha256(content.encode()).hexdigest())
            for heading, content in COMPOSER_BEHAVIOR_SECTIONS]


def attach_composer_behavior(payload):
    """Replace optional/manual selections with the mandatory conversion context."""
    result = {**payload, "composer_behavior_evidence": required_composer_behavior()}
    relationship = payload.get("relationship_context")
    if isinstance(relationship, str):
        try:
            context = json.loads(relationship)
        except ValueError:
            context = None
        if isinstance(context, dict) and "composer_behavior_evidence" in context:
            result["relationship_context"] = json.dumps({key: value for key, value in context.items() if key != "composer_behavior_evidence"})
    return result


def behavior_context(document_path, headings):
    """Return requested Markdown sections, rejecting missing or ambiguous headings."""
    if not headings:
        return []
    path = Path(document_path)
    content = path.read_text(encoding="utf-8-sig")
    matches = list(re.finditer(r"^(#{2,6})\s+(.+?)\s*$", content, re.MULTILINE))
    result = []
    for heading in dict.fromkeys(headings):
        found = [index for index, match in enumerate(matches) if match.group(2) == heading]
        if len(found) != 1:
            raise ValueError("Behavior document requires one matching heading: " + heading)
        index = found[0]
        start = matches[index]
        end = next((match.start() for match in matches[index + 1:] if len(match.group(1)) <= len(start.group(1))), len(content))
        excerpt = content[start.start():end].strip()
        result.append(dict(document=str(path.resolve()), heading=heading, content=excerpt,
                           content_hash=hashlib.sha256(excerpt.encode()).hexdigest()))
    return result


def compact_behavior_evidence(records):
    """Store each documentation excerpt once, retaining references on every contract."""
    documents, compact = {}, []
    for record in records:
        references = []
        for evidence in record["behavior_evidence"]:
            key = (evidence["document"], evidence["heading"], evidence["content_hash"])
            documents[key] = evidence
            references.append({name: value for name, value in evidence.items() if name != "content"})
        compact.append({**record, "behavior_evidence": references})
    return compact, list(documents.values())
