"""Reject ambiguous saved approval checkpoints from the previous gate layout."""
from pathlib import Path
from tools.state_store_tools.operation_progress import active_operation,operation_directory


def check_gate_numbering(conn, run_id, directory, phase):
    """Never reinterpret an old final Gate 4 or creation Gate 5 approval as the new role."""
    if not phase.startswith(('gate_4_','gate_5_')):return
    current=active_operation(conn,run_id)
    folder=operation_directory(directory,current['operation_key']) if current else Path(directory)
    if not (folder/'reports').exists():folder=Path(directory)
    old,new=(('7_final_validation/gate_4_report.txt','6_service_generation_and_validation/gate_4_report.txt')
        if phase.startswith('gate_4_') else
        ('6_service_generation_and_validation/gate_5_report.txt','7_final_validation/gate_5_report.txt'))
    def creation_report(path):
        return 'Create microservices' in path.read_text(encoding='utf-8').split('\n',1)[0]
    expected=folder/'reports'/new
    expected_creation=phase.startswith('gate_4_')
    valid_current=expected.is_file() and creation_report(expected)==expected_creation
    legacy=any(p.is_file() and creation_report(p)!=expected_creation
               for p in (folder/'reports'/old,expected))
    if legacy and not valid_current:
        raise ValueError('Saved approval checkpoint uses the previous Gate 4/5 numbering. '
            'Use a revised run with the accepted native artifacts or explicitly migrate this checkpoint; '
            'old approvals cannot authorize a different gate role.')
