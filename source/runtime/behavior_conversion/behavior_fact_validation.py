"""Validate evidence references mechanically without claiming semantic completeness."""

from tools.component_inventory_tools.identity import stable_id


def validate_citations(citations, sources):
    """Reject nonexistent revisions and excerpts, including policy-as-source confusion."""
    catalog = {source['identity']: source for source in sources}
    for citation in citations:
        source = catalog.get(citation.identity)
        if not source or source['content_hash'] != citation.content_hash or not citation.excerpt.strip():
            raise ValueError('Behavior citation refers to unavailable source revision: ' + citation.identity)
        if citation.excerpt not in source['content']:
            raise ValueError('Behavior excerpt is absent from cited source: ' + citation.identity)


def validate_specification(specification, sources):
    """Bind stable fact IDs to validated content; unknown evidence stays unresolved."""
    if not specification.facts and not specification.unresolved_questions:
        raise ValueError('Behavior extraction must describe evidence or identify a material gap')
    for fact in specification.facts:
        validate_citations(fact.evidence, sources)
        if any(c.identity.startswith('compatibility-policy:') for c in fact.evidence) != (
                fact.origin == 'compatibility_policy'):
            raise ValueError('Behavior fact must distinguish policy from source evidence')
        fact.fact_id = 'behavior-' + stable_id(fact.model_dump(mode='json', exclude={'fact_id'}))


def validate_comparison(comparison, specification, sources, files):
    """Require complete fact coverage and actual source/candidate locations."""
    expected = {fact.fact_id for fact in specification.facts}
    seen = []
    for finding in comparison.findings:
        if finding.fact_id is not None:
            if finding.fact_id not in expected:
                raise ValueError('Comparison cites an unknown behavior fact')
            seen.append(finding.fact_id)
        elif finding.status in {'matched', 'non_behavioral_difference'}:
            if finding.status == 'matched':
                raise ValueError('Matched findings require a supplied fact ID')
        if finding.fact_id and finding.status == 'non_behavioral_difference':
            raise ValueError('Source behavior obligations cannot be dismissed as stylistic')
        if finding.status != 'non_behavioral_difference':
            if not finding.source_evidence:
                raise ValueError('Behavior comparison requires source evidence')
        if finding.source_evidence:
            validate_citations(finding.source_evidence, sources)
        for location in finding.generated_evidence:
            if location.path not in files or not location.excerpt.strip() or location.excerpt not in files[location.path]:
                raise ValueError('Comparison cites nonexistent generated code')
        if finding.status in {'matched', 'changed', 'invented_behavior'} and not any(
                location.path.startswith('src/main/java/') for location in finding.generated_evidence):
            raise ValueError('Comparison must cite candidate implementation')
        if finding.status in {'missing', 'changed', 'invented_behavior'} and not (
                finding.trigger.strip() and finding.consequence.strip()):
            raise ValueError('Blocking behavior mismatch requires trigger and observable consequence')
    if set(seen) != expected or len(seen) != len(expected):
        raise ValueError('Comparison must assess every behavior fact exactly once')


def validate_implementations(bundle, specification):
    """Check claimed fact-to-code links, without interpreting their semantics."""
    expected = {fact.fact_id for fact in specification.facts}
    if set(bundle.behavior_implementations) != expected:
        raise ValueError('Candidate must map every behavior fact to its implementation')
    files = {item.path: item.content for item in bundle.files}
    for locations in bundle.behavior_implementations.values():
        if not locations:
            raise ValueError('Behavior implementation locations cannot be empty')
        for location in locations:
            if not location.path.startswith('src/main/java/') or location.path not in files or not (
                    location.excerpt.strip() and location.excerpt in files[location.path]):
                raise ValueError('Behavior implementation location is absent from candidate code')
