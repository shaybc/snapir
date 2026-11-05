"""Adapt existing collectors to wizard headings, remembered answers and local navigation."""

from copy import deepcopy

from cli.interactive import SelectionCancelled


class WizardBack(Exception):
    """Return to the previous section without committing its unfinished edits."""


class WizardInputs:
    """Wrap canonical CLI input functions; commit remembered answers only on Next."""

    def __init__(self, draft, api, names):
        """Attach the draft to the canonical input API and section labels."""
        self.draft, self.api, self.names = draft, api, names
        self.pending = {}
        self.feedback = ''

    def begin(self, retain=False):
        """Restore committed answers before a new attempt at the current section."""
        if not retain:
            self.pending = deepcopy(self.draft.answers.get(self.draft.section, {}))
        self.api.clear_screen()
        print(self.heading(), flush=True)

    def heading(self):
        """Identify the draft and section on every input screen."""
        name = self.pending.get('Config name (for example bank_demo)') or self.draft.values().get('_name', '(new)')
        from cli.configuration_review import safe_value
        notice = ('\nA new map will be generated when you start a migration. No mapping is running now.'
                  if self.pending.get('@menu:Composer map') == 'create' else '')
        return (f'Create configuration: {safe_value(name)}\n'
                f'Section {self.draft.section + 1} of {len(self.names)}: {self.names[self.draft.section]}\n'
                f'Completed sections: {len(self.draft.sections)}; changes are not saved.' + notice +
                ('\n' + safe_value(self.feedback) if self.feedback else ''))

    def text(self, title, default=''):
        """Remember text by its stable collector label, with blank Enter retaining its value."""
        value = self.api.prompt_text(title, self.pending.get(title, default),
                                     heading=self.heading(), allow_back=self.draft.section > 0)
        self.pending[title] = value
        return value

    def menu(self, title, options):
        """Remember section choices and provide visible Back/Cancel actions."""
        key = '@menu:' + title
        choices = list(options)
        if self.draft.section > 0:
            choices.append(('_back', 'Back (discard unfinished section edits)'))
        choices.append(('_cancel', 'Cancel configuration'))
        value = self.api.select_option(title, choices, initial=self.pending.get(key),
                                       heading=self.heading(), clear_after_selection=False)
        if value == '_back':
            raise WizardBack
        if value == '_cancel':
            raise SelectionCancelled
        self.pending[key] = value
        return value

    def multiple(self, title, options, **kwargs):
        """Restore checked values while dropping only choices no longer available."""
        key = '@multiple:' + title
        available = {value for value, _ in options}
        initial = [value for value in self.pending.get(key, []) if value in available]
        value = self.api.select_multiple(title, options, initial=initial, heading=self.heading(),
                                         allow_back=self.draft.section > 0, clear_after_selection=False, **kwargs)
        self.pending[key] = value
        return value

    def next(self):
        """Require an explicit section commit, distinct from finishing the final field."""
        return self.menu('Section complete', [('next', 'Next - keep these section answers')])

    def discard(self):
        """Confirm draft cancellation without allowing Escape to silently discard it."""
        while True:
            try:
                result = self.api.select_option('Discard unsaved configuration?',
                    [('continue', 'Continue editing'), ('discard', 'Discard configuration')],
                    heading=self.heading(), clear_after_selection=False)
                return result == 'discard'
            except SelectionCancelled as exc:
                return exc.input_closed
