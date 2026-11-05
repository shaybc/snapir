"""Collect checkbox selections with arrow keys, Space, and Done above the values."""

from cli.interactive import SelectionCancelled
from cli.terminal_display import clear_screen, separate_result_from_menu


def select_multiple(title: str, options: list[tuple[str, str]], *, select_all: bool = False,
                    filterable: bool = False, initial=None, heading=None, allow_back=False,
                    clear_after_selection=True) -> list[str]:
    """Return checked values on Done, refusing an empty selection; cancellation writes nothing.

    Optional filtering matches labels without discarding hidden selections. Select all
    always applies to the complete option list, and results retain the input order.
    """
    from prompt_toolkit.application import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.processors import BeforeInput

    if not options:
        raise ValueError(f"{title}: no options available")
    operation_start = 1 + int(filterable) + int(select_all)
    visible = list(options)
    selected: set[str] = set(initial or []) & {value for value, _ in options}
    selected_index = 0
    operation_index = 0
    message = ""
    bindings = KeyBindings()

    def operation_text():
        if not visible:
            return [("", "    No matching operations")]
        return [("reverse" if selected_index == operation_start + index else "",
                 f"{'[x]' if value in selected else '[ ]'} {label}\n")
                for index, (value, label) in enumerate(visible)]

    operation_control = FormattedTextControl(
        operation_text, focusable=True, show_cursor=False,
        get_cursor_position=lambda: Point(0, operation_index))
    operation_window = Window(operation_control, wrap_lines=False)
    done_control = FormattedTextControl(
        lambda: [("reverse" if selected_index == 0 else "", "    Next" if heading else "    Done")],
        focusable=True, show_cursor=False)

    def focus_selection():
        nonlocal operation_index
        if selected_index == 0:
            layout.focus(done_control)
        elif filterable and selected_index == 1:
            layout.focus(filter_control)
        elif select_all and selected_index == operation_start - 1:
            layout.focus(all_control)
        else:
            operation_index = selected_index - operation_start
            layout.focus(operation_control)

    def filter_changed(buffer):
        nonlocal visible, selected_index, operation_index
        previous = visible[operation_index][0] if visible else None
        visible = [(value, label) for value, label in options if buffer.text.casefold() in label.casefold()]
        operation_index = next((index for index, (value, _) in enumerate(visible) if value == previous), 0)
        if selected_index >= operation_start:
            selected_index = operation_start + operation_index if visible else 1
        operation_window.vertical_scroll = 0
        focus_selection()

    filter_buffer = Buffer(multiline=False, on_text_changed=filter_changed)
    filter_control = BufferControl(filter_buffer, input_processors=[BeforeInput("    Filter: ")])
    all_control = FormattedTextControl(
        lambda: [("reverse" if selected_index == operation_start - 1 else "",
                  f"{'[x]' if len(selected) == len(options) else '[ ]'} "
                  f"{'Select all operations' if filterable else 'Select all'}")],
        focusable=True, show_cursor=False)
    header = [Window(done_control, height=1)]
    if filterable:
        header.append(Window(filter_control, height=1))
    if select_all:
        header.append(Window(all_control, height=1))
    header.append(Window(FormattedTextControl("    ────────────────────────"), height=1))

    def status_text():
        count = f"{len(visible)} matches of {len(options)} · {len(selected)} selected" if filterable else f"{len(selected)} selected"
        return f"{message} · {count}" if message else count

    wizard_header = [Window(FormattedTextControl(heading + '\nINPUT REQUIRED\n' + title), wrap_lines=True)] if heading else []
    navigation = ([Window(FormattedTextControl('Back: Ctrl+B (discard unfinished section edits)' if allow_back else
                                              'First section'), wrap_lines=True),
                   Window(FormattedTextControl('Cancel: Esc   Enter on Next   Space: toggle   Type to filter' if filterable else
                                              'Cancel: Esc   Enter on Next   Space: toggle'), wrap_lines=True)] if heading else [])
    layout = Layout(HSplit(wizard_header + header + [operation_window,
                                   Window(FormattedTextControl(status_text), height=1)] + navigation),
                    focused_element=done_control)

    def move_selection(offset):
        nonlocal selected_index, operation_index
        entering_operations = selected_index == operation_start - 1 and offset == 1 and visible
        selected_index = (selected_index + offset) % (operation_start + len(visible))
        if selected_index == 0 and offset == 1:
            operation_index = 0
        if entering_operations:
            selected_index += operation_index
        focus_selection()

    @bindings.add("up")
    def move_up(event):
        move_selection(-1)

    @bindings.add("down")
    def move_down(event):
        move_selection(1)

    @bindings.add("pageup")
    @bindings.add("pagedown")
    def move_page(event):
        nonlocal selected_index
        if not visible:
            return
        height = operation_window.render_info.window_height if operation_window.render_info else 1
        offset = height if event.key_sequence[0].key == "pagedown" else -height
        selected_index = max(operation_start, min(operation_start + len(visible) - 1,
                                                 max(operation_start, selected_index) + offset))
        focus_selection()

    editing_filter = Condition(lambda: filterable and selected_index == 1)

    @bindings.add("home", filter=~editing_filter)
    @bindings.add("end", filter=~editing_filter)
    def move_boundary(event):
        nonlocal selected_index, operation_index
        selected_index = 0 if event.key_sequence[0].key == "home" else operation_start + len(visible) - 1
        if selected_index == 0:
            operation_index = 0
        focus_selection()

    @bindings.add("<any>", filter=Condition(lambda: filterable) & ~editing_filter)
    def start_filter(event):
        nonlocal selected_index
        if event.data.isprintable():
            selected_index = 1
            focus_selection()
            filter_buffer.insert_text(event.data)

    @bindings.add(" ", filter=~editing_filter)
    def toggle(event):
        nonlocal message
        message = ""
        if selected_index == 0:
            return
        if select_all and selected_index == operation_start - 1:
            if len(selected) == len(options):
                selected.clear()
            else:
                selected.update(value for value, _ in options)
        elif selected_index >= operation_start and visible:
            value = visible[selected_index - operation_start][0]
            if value in selected:
                selected.remove(value)
            else:
                selected.add(value)

    @bindings.add("enter", eager=True)
    def finish(event):
        nonlocal message
        if selected_index != 0:
            return
        if not selected:
            message = "Select at least one item before Done."
            return
        event.app.exit(result=[value for value, _ in options if value in selected])

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def cancel(event):
        event.app.exit(result=None)

    if allow_back:
        @bindings.add('c-b', eager=True)
        def back(event):
            from cli.configuration_inputs import WizardBack
            event.app.exit(exception=WizardBack())

    if not heading:
        separate_result_from_menu()
        print(f"{title} (Up/Down to move, Space to toggle, Page Up/Down to scroll, "
              f"Home/End to jump, {'type to filter, ' if filterable else ''}Enter on Done, Esc to cancel)")
    try:
        result = Application(layout=layout, key_bindings=bindings, full_screen=bool(heading)).run()
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
