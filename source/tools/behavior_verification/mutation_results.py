"""Interpret PIT results as test-strength evidence, never behavioral equivalence."""
from collections import Counter
from xml.etree import ElementTree as ET


def read_mutations(path, recommended_score):
    """Keep survivors, uncovered mutations and execution errors distinct from killed mutants."""
    root = ET.parse(path).getroot()
    if root.tag != 'mutations': raise ValueError('Unexpected PIT report root')
    mutations = []
    for node in root.findall('mutation'):
        status = node.get('status')
        if status not in {'KILLED','SURVIVED','NO_COVERAGE','TIMED_OUT','NON_VIABLE','MEMORY_ERROR','RUN_ERROR','NOT_STARTED'}:
            raise ValueError('Unknown PIT mutation status: ' + str(status))
        mutations.append(dict(status=status, source_file=node.findtext('sourceFile'), class_name=node.findtext('mutatedClass'),
            method=node.findtext('mutatedMethod'), line=node.findtext('lineNumber'), mutator=node.findtext('mutator'),
            description=node.findtext('description'), killing_test=node.findtext('killingTest')))
    counts = Counter(item['status'] for item in mutations)
    denominator = sum(counts[name] for name in ('KILLED','SURVIVED','NO_COVERAGE'))
    score = round(100 * counts['KILLED'] / denominator, 2) if denominator else None
    errors = sum(counts[name] for name in ('TIMED_OUT','NON_VIABLE','MEMORY_ERROR','RUN_ERROR','NOT_STARTED'))
    status = 'incomplete' if errors else 'completed' if mutations else 'no_mutations'
    recommendations = []
    if counts['SURVIVED']: recommendations.append('Add assertions for surviving mutations at the listed methods and lines.')
    if counts['NO_COVERAGE']: recommendations.append('Add tests that execute the uncovered methods and lines.')
    if errors: recommendations.append('Resolve mutation execution errors before interpreting an overall score.')
    if not mutations: recommendations.append('No mutations were measured; no strength score is available.')
    if score is not None and score < recommended_score: recommendations.append('Add tests toward the advisory score of ' + str(recommended_score) + '%.')
    return dict(status=status, counts=dict(counts), total=len(mutations), score=score, recommendations=recommendations,
                score_definition='KILLED / (KILLED + SURVIVED + NO_COVERAGE); execution errors excluded', mutations=mutations)
