"""Complete missing CLI arguments using cancellable arrow-key menus."""

from pathlib import Path

from runtime.project_paths import project_root
import sys

from cli.discovery import discover_configurations, discover_runs
from cli.terminal_display import clear_screen, separate_result_from_menu
from cli.status_discovery import discover_status_runs


class SelectionCancelled(Exception):
    """Signal cancellation before the selected command begins execution."""

    def __init__(self, *args, input_closed=False):
        super().__init__(*args)
        self.input_closed = input_closed


def is_interactive() -> bool:
    """Require terminal input and output before displaying a menu."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def select_option(title: str, options: list[tuple[str, str]], *, clear_after_selection: bool = True,
                  initial=None, heading=None, details=None, filterable=False) -> str:
    """Select with Up/Down and Enter; cancel with Escape or Ctrl+C."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window, HSplit
    from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout.processors import BeforeInput

    if not options:
        raise ValueError(f"{title}: no options available")
    selected_index = next((index for index, (value, _) in enumerate(options) if value == initial), 0)
    visible = list(options)
    bindings = KeyBindings()

    def menu_text():
        return [("reverse" if index == selected_index else "", f"{'>' if index == selected_index else ' '} {label}\n")
                for index, (_, label) in enumerate(visible)] or [('', 'No matching operations')]

    control = FormattedTextControl(menu_text, focusable=True, get_cursor_position=lambda: Point(0, selected_index))
    menu = Window(control, wrap_lines=bool(heading),
                  get_vertical_scroll=(lambda window: max(0, selected_index -
                      (window.render_info.window_height if window.render_info else 1) + 1)) if filterable else None)
    summary_scroll = 0
    def summary_text():
        from prompt_toolkit.application.current import get_app
        from cli.configuration_review import wrapped_summary
        return wrapped_summary(details or [], get_app().output.get_size().columns)
    summary = Window(FormattedTextControl(summary_text, show_cursor=False,
                     get_cursor_position=lambda: Point(0, summary_scroll)), wrap_lines=False,
                     get_vertical_scroll=lambda window: summary_scroll, allow_scroll_beyond_bottom=True)
    def filtered(buffer):
        nonlocal visible, selected_index
        visible = [(value, label) for value, label in options if buffer.text.casefold() in label.casefold()]
        selected_index = 0
        menu.vertical_scroll = 0
    search = Buffer(on_text_changed=filtered)
    search_control = BufferControl(search, input_processors=[BeforeInput('Filter: ')])

    @bindings.add("up")
    def move_up(event):
        nonlocal selected_index
        selected_index = (selected_index - 1) % max(1, len(visible))

    @bindings.add("down")
    def move_down(event):
        nonlocal selected_index
        selected_index = (selected_index + 1) % max(1, len(visible))

    @bindings.add("enter", eager=True)
    def accept(event):
        if visible:
            event.app.exit(result=visible[selected_index][0])

    if details:
        @bindings.add('pageup')
        @bindings.add('pagedown')
        def scroll_summary(event):
            nonlocal summary_scroll
            height = summary.render_info.window_height if summary.render_info else 5
            offset = height if event.key_sequence[0].key == 'pagedown' else -height
            summary_scroll = max(0, min(max(0, len(summary_text().splitlines()) - height), summary_scroll + offset))

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def cancel(event):
        event.app.exit(result=None)

    if heading:
        layout = HSplit([Window(FormattedTextControl(heading + '\nINPUT REQUIRED\n' + title), wrap_lines=True, dont_extend_height=True),
                         *([summary] if details else []),
                         *([Window(search_control, height=1)] if filterable else []),
                         menu,
                         Window(FormattedTextControl('Up/Down: select   Enter: continue   Esc: cancel' +
                             ('   Page Up/Down: review settings' if details else '')), wrap_lines=True, dont_extend_height=True)])
        # Keep actions visible even when the settings summary is long.
        if details:
            from prompt_toolkit.layout.dimension import Dimension
            menu.height = Dimension(min=min(5, len(options)), max=min(8, len(options)))
    else:
        layout = menu
        separate_result_from_menu()
        print(f"{title} (Up/Down to move, Enter to select, Esc to cancel)")
    try:
        result = Application(layout=Layout(layout, focused_element=search_control if filterable else control),
                             key_bindings=bindings, full_screen=bool(heading)).run()
    except EOFError as exc:
        raise SelectionCancelled(input_closed=True) from exc
    except KeyboardInterrupt as exc:
        raise SelectionCancelled from exc
    finally:
        if clear_after_selection:
            clear_screen()
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
        if args.command in {"status", "resume", "approve", "reject"}:
            return
    if args.command == "documentation":
        args.command = select_option("Help / README", [
            ("help", "Show help screen"), ("readme", "Open README in browser"),
        ])
    if args.command in {"create_config", "help", "readme", "exit"}:
        return
    if not args.config:
        args.config = select_configuration()


def select_configuration(initial=None):
    """Choose a saved configuration, optionally restoring the previous cursor choice."""
    root = project_root()
    configurations = discover_configurations(root)
    if not configurations:
        raise ValueError("No YAML configurations found in config or configs folders; supply --config")
    kwargs = {'initial': initial} if initial is not None else {}
    return select_option("Select a configuration", [
        (str(path), str(path.relative_to(root))) for path in configurations
    ], **kwargs)


def complete_run_selection(args, profile) -> None:
    """Choose an existing run when the selected command requires one."""
    if args.run_id or args.command == "start" or not is_interactive():
        return
    options = discover_runs(profile.output_root, resumable_only=args.command == "resume")
    if not options:
        raise ValueError(f"No current-layout runs found in {profile.output_root}")
    selected = select_option("Select a run", options)
    args.run_id = selected or None


def select_status_run() -> Path:
    """Choose a persisted run without selecting or validating a migration configuration."""
    return _select_saved_run(resumable_only=False)


def select_resume_run() -> Path:
    """Choose a supported checkpoint with a saved profile independently of original YAML."""
    return _select_saved_run(resumable_only=True)


def select_gate_run() -> Path:
    """Choose a run waiting at a pending or rejected review gate without an original config."""
    options = discover_status_runs(project_root(), awaiting_gate_only=True)
    if not options:
        raise ValueError("No gate awaiting a decision was found in the default or configured output roots")
    return Path(select_option("Select a run awaiting a gate decision", options))


def _select_saved_run(*, resumable_only: bool) -> Path:
    options = discover_status_runs(project_root(), resumable_only=resumable_only)
    if not options:
        if resumable_only:
            raise ValueError("No resumable runs with saved profiles found in the default or configured output roots")
        raise ValueError("No readable current-layout runs found in the default or configured output roots")
    return Path(select_option("Select a run", options))
