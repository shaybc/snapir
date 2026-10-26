"""Record measured preparation evidence without granting scoped conversion readiness."""

import os
from datetime import datetime, timezone


def process_peak_memory():
    """Read the process lifetime peak RSS; unavailable counters never become zero."""
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes

            class MemoryCounters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                        'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = MemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                raise OSError(ctypes.get_last_error(), 'GetProcessMemoryInfo failed')
            value = counters.PeakWorkingSetSize
        else:
            import resource
            import sys
            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            value *= 1 if sys.platform == 'darwin' else 1024
        return dict(bytes=value, scope='process_lifetime_peak_rss', error=None)
    except (ImportError, AttributeError, OSError) as exc:
        return dict(bytes=None, scope='process_lifetime_peak_rss', error=str(exc))


def preparation_acceptance(conn, run_id, preparation, elapsed_seconds):
    """Summarize one measured attempt; native and enterprise gates remain unverified."""
    counts = {}
    for name, table in (
        ('source_definitions', 'scoped_source_definitions'),
        ('entity_usages', 'scoped_entity_usages'),
        ('operation_contexts', 'scoped_operation_contexts'),
        ('context_bindings', 'scoped_context_bindings'),
    ):
        counts[name] = conn.execute(f'SELECT count(*) FROM {table} WHERE run_id=?', (run_id,)).fetchone()[0]
    counts['selected_contexts'] = conn.execute(
        'SELECT count(*) FROM scoped_operation_contexts WHERE run_id=? AND selected=1', (run_id,)).fetchone()[0]
    operations = preparation.get('operations', {})
    counts['attempted_contexts'] = len(operations)
    counts['prepared_contexts'] = sum(item.get('status') == 'prepared' for item in operations.values())
    counts['blocked_contexts'] = sum(item.get('status') == 'blocked' for item in operations.values())
    counts['reused_contexts'] = len(preparation.get('reused_contexts', []))
    error = preparation.get('preparation_error')
    ready = bool(operations) and not error and counts['prepared_contexts'] == len(operations)
    return dict(report_version=1, run_id=run_id, recorded_at=datetime.now(timezone.utc).isoformat(),
        phase='preparation', conversion_enabled=False, acceptance_complete=False,
        preparation_status='passed' if ready else 'blocked', preparation_error=error,
        elapsed_seconds=elapsed_seconds, peak_memory=process_peak_memory(), counts=counts,
        unverified_gates=[
            'behavior runtime: qualified generation, review, compilation and executable behavior checks',
            'assembly runtime: qualified generation, review, compilation and executable behavior checks',
            'approved enterprise input: import and conversion time, memory and progress',
        ], measurement_limits=[
            'Elapsed time covers this preparation attempt only; intake and native conversion are excluded.',
            'Peak RSS covers the process lifetime, including earlier work; it is not a preparation-only peak.',
            'Input size and preparation success do not establish enterprise or native conversion acceptance.',
        ])
