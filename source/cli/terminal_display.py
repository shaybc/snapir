"""Keep interactive screens clean while leaving redirected output unchanged."""

import sys


def _is_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def clear_screen() -> None:
    """Clear completed interactive content with the terminal's native output backend."""
    if _is_terminal():
        from prompt_toolkit.shortcuts import clear

        clear()


def separate_result_from_menu() -> None:
    """Leave two empty lines above an interactive menu without erasing action results."""
    if _is_terminal():
        print("\n")
