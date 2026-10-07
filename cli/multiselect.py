"""Collect checkbox selections with arrow keys, Space, and Done above the values."""

from cli.interactive import SelectionCancelled


def select_multiple(title: str, options: list[tuple[str, str]], *, select_all: bool = False) -> list[str]:
    """Return checked values on Done, refusing an empty selection; cancellation writes nothing."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    if not options:
        raise ValueError(f"{title}: no options available")
    rows = [None] + ([None] if select_all else []) + [value for value, _ in options]
    labels = ["Done"] + (["Select all"] if select_all else []) + [label for _, label in options]
    selected: set[str] = set()
    selected_index = 0
    message = ""
    bindings = KeyBindings()

    def menu_text():
        result = []
        for index, label in enumerate(labels):
            if index == 0:
                marker = "   "
            else:
                checked = len(selected) == len(options) if select_all and index == 1 else rows[index] in selected
                marker = "[x]" if checked else "[ ]"
            result.append(("reverse" if index == selected_index else "", f"{marker} {label}\n"))
            if index == (1 if select_all else 0):
                result.append(("", "    ────────────────────────\n"))
        result.append(("", message))
        return result

    @bindings.add("up")
    def move_up(event):
        nonlocal selected_index
        selected_index = (selected_index - 1) % len(rows)

    @bindings.add("down")
    def move_down(event):
        nonlocal selected_index
        selected_index = (selected_index + 1) % len(rows)

    @bindings.add(" ")
    def toggle(event):
        nonlocal message
        message = ""
        if selected_index == 0:
            return
        if select_all and selected_index == 1:
            if len(selected) == len(options):
                selected.clear()
            else:
                selected.update(value for value, _ in options)
        elif rows[selected_index] in selected:
            selected.remove(rows[selected_index])
        else:
            selected.add(rows[selected_index])

    @bindings.add("enter", eager=True)
    def finish(event):
        nonlocal message
        if selected_index != 0:
            return
        if not selected:
            message = "Select at least one item before Done.\n"
            return
        event.app.exit(result=[value for value, _ in options if value in selected])

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def cancel(event):
        event.app.exit(result=None)

    print(f"{title} (Up/Down to move, Space to toggle, Enter on Done, Esc to cancel)")
    try:
        result = Application(layout=Layout(Window(FormattedTextControl(menu_text))), key_bindings=bindings).run()
    except (KeyboardInterrupt, EOFError) as exc:
        raise SelectionCancelled from exc
    if result is None:
        raise SelectionCancelled
    return result
