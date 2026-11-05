"""Measure current and peak resident memory without optional monitoring dependencies."""

import os


def memory_usage(process_id=None):
    """Return OS-reported Python RSS/peak bytes when the platform exposes them."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'rss', 'peakPaged', 'paged', 'peakNonpaged', 'nonpaged', 'pagefile', 'peakPagefile')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        api = ctypes.WinDLL('psapi', use_last_error=True)
        api.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        handle = kernel.OpenProcess(0x1010, False, process_id) if process_id is not None else kernel.GetCurrentProcess()
        try:
            if handle and api.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return dict(python_rss_bytes=counters.rss, python_peak_rss_bytes=counters.peak)
        finally:
            if process_id is not None and handle:
                kernel.CloseHandle(handle)
    elif os.path.exists('/proc/' + str(process_id or 'self') + '/status'):
        try:
            with open('/proc/' + str(process_id or 'self') + '/status') as stream:
                fields = {line.split(':')[0]: line.split(':')[1].strip() for line in stream if line.startswith(('VmRSS:', 'VmHWM:'))}
            return dict(python_rss_bytes=int(fields['VmRSS'].split()[0]) * 1024,
                        python_peak_rss_bytes=int(fields['VmHWM'].split()[0]) * 1024)
        except (OSError, KeyError):
            return {}
    return {}
