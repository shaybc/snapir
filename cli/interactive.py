"""Complete missing CLI arguments using cancellable arrow-key menus."""

from pathlib import Path
import sys

from cli.discovery import discover_configurations, discover_runs


class SelectionCancelled(Exception):
    """Signal cancellation before the selected command begins execution."""


def is_interactive() -> bool:
    """Require terminal input and output before displaying a menu."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def select_option(title: str, options: list[tuple[str, str]]) -> str:
    """Select with Up/Down and Enter; cancel with Escape or Ctrl+C."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    if not options:
        raise ValueError(f"{title}: no options available")
    selected_index = 0
    bindings = KeyBindings()

    def menu_text():
        return [("reverse" if index == selected_index else "", f"{'>' if index == selected_index else ' '} {label}\n")
                for index, (_, label) in enumerate(options)]

    @bindings.add("up")
    def move_up(event):
        nonlocal selected_index
        selected_index = (selected_index - 1) % len(options)

    @bindings.add("down")
    def move_down(event):
        nonlocal selected_index
        selected_index = (selected_index + 1) % len(options)

    @bindings.add("enter", eager=True)
    def accept(event):
        event.app.exit(result=options[selected_index][0])

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def cancel(event):
        event.app.exit(result=None)

    print(f"{title} (Up/Down to move, Enter to select, Esc to cancel)")
    try:
        result = Application(layout=Layout(Window(FormattedTextControl(menu_text))), key_bindings=bindings).run()
    except (KeyboardInterrupt, EOFError) as exc:
        raise SelectionCancelled from exc
    if result is None:
        raise SelectionCancelled
    return result


def complete_arguments(args, parser) -> None:
    """Fill missing command/config while preserving supplied command meanings."""
    if not is_interactive():
        if not args.command or not args.config:
            parser.error("command and --config are required without an interactive terminal")
        return
    if not args.command:
        args.command = select_option("What would you like to do?", [
            ("create_config", "Create a new config"),
            ("start", "Start a new migration"), ("resume", "Resume a migration"),
            ("status", "View run status"), ("approve", "Approve a gate"),
            ("reject", "Reject a gate"),
            ("documentation", "Help / README"), ("exit", "Exit"),
        ])
    if args.command == "documentation":
        args.command = select_option("Help / README", [
            ("help", "Show help screen"), ("readme", "Open README in browser"),
        ])
    if args.command in {"create_config", "help", "readme", "exit"}:
        return
    if not args.config:
        root = Path(__file__).resolve().parent.parent
        configurations = discover_configurations(root)
        if not configurations:
            raise ValueError("No YAML configurations found in config or configs folders; supply --config")
        args.config = select_option("Select a configuration", [
            (str(path), str(path.relative_to(root))) for path in configurations
        ])


def complete_run_selection(args, profile) -> None:
    """Choose an existing run when the selected command requires one."""
    if args.run_id or args.command == "start" or not is_interactive():
        return
    options = discover_runs(profile.output_root, resumable_only=args.command == "resume")
    if not options:
        raise ValueError(f"No current-layout runs found in {profile.output_root}")
    selected = select_option("Select a run", options)
    args.run_id = selected or None
