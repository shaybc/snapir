"""Short human reports and machine-readable repair feedback with explicit static-analysis limits."""
from comparator.models import SCHEMA, VERSION, save


def finish(inputs, targets, results, issues, calls, warnings, run):
    """Choose a cautious aggregate decision; incomplete work never becomes consistency approval."""
    findings=[item for item in results if item.get('verdict')=='difference' and item.get('adjudicated')]
    unresolved=[item for item in results if item.get('verdict')=='inconclusive']
    complete=not issues and not unresolved
    decision='differences_found' if findings else 'consistent_in_review' if complete else 'inconclusive'
    remarks=[dict(message=item['explanation'],suggested_action=item['suggested_action'],
                  counterexample=item.get('counterexample',''),original_evidence=item.get('original_evidence',[]),
                  generated_evidence=item.get('generated_evidence',[])) for item in findings+unresolved]
    remarks.extend(dict(message=issue,suggested_action='Supply missing evidence or resume with sufficient analysis budget.') for issue in issues)
    report=dict(schema_version=SCHEMA,tool_version=VERSION,evidence_level='static_analysis',decision=decision,
        complete=complete,input_hash=inputs['input_hash'],files=inputs['files'],targets=targets,
        findings=findings,remarks=remarks,coverage=dict(reviewed=len(results),inconclusive=len(unresolved),unreviewed=issues),
        model_calls=calls,warnings=warnings,
        limitations=['Read-only AI-assisted review; no compilation, execution, tests or equivalence proof.',
                     'AST fact accounting is syntactic coverage, not proof that the behavior inventory is complete.',
                     'Behavior of runtime-selected child implementations beyond supplied source is not verified.',
                     'Interactions are selected by indexed calls and shared state; other interactions may remain.'])
    save(run/'report.json',report)
    save(run/'repair-feedback.json',dict(decision=decision,evidence_level='static_analysis',remarks=remarks,
        instruction='These are static findings. Correct supported differences only; clarify inconclusive evidence before changing behavior.'))
    lines=['# Java behavior comparison', '', 'Decision: '+decision, 'Evidence: static analysis only',
           'Complete within selected scope: '+str(complete), '', 'Findings and unresolved evidence:']
    lines.extend('- '+remark['message'] for remark in remarks[:20])
    if len(remarks)>20: lines.append('- Additional remarks are retained in report.json.')
    if not remarks: lines.append('- No confirmed differences found in the inspected scope. This is not proof of equivalence.')
    (run/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report
