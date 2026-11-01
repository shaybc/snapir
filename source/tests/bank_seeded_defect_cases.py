"""Small reproducible bank boundary corpora and explicit test-only source mutations."""
from pathlib import Path
from xml.sax.saxutils import escape
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding


FIXTURES = Path(__file__).parent / 'fixtures'
SETTINGS = 'com.ibm.dse.base.SchemaValidationSettings'


def native_binding(kind):
    """Read independent fixtures; never copy original implementing classes to the native side."""
    names = ['BankRequestBoundaryAdapter'] if kind == 'request_unformat' else [
        'BankErrorResponseBoundaryAdapter', 'BankSchemaValidationSettings']
    return BoundaryHarnessBinding(adapter_class='fixture.' + names[0],
        sources=[dict(path='fixture/' + name + '.java', content=(FIXTURES / (name + '.java')).read_text(encoding='utf-8'))
                 for name in names], settings_bindings={} if kind == 'request_unformat' else {
                     SETTINGS + '.configure': {'class': 'fixture.BankSchemaValidationSettings', 'method': 'configure'}})


def request_cases():
    """Include successful controls and witnesses for mandatory, zero and padding defects."""
    baseline = dict(ClientId='123', AccountNumber='0000000042', SessionToken='session',
                    FromDate='20240101', ToDate='20240102', MaxTransactions='0005')
    variants = [ ('valid', {}), ('client-empty', dict(ClientId='')), ('client-missing', dict(ClientId=None)),
        ('maximum-empty', dict(MaxTransactions='')), ('maximum-missing', dict(MaxTransactions=None)),
        ('account-trailing-zero', dict(AccountNumber='0000012300')), ('account-all-zero', dict(AccountNumber='0000000000')),
        ('maximum-zeroes', dict(MaxTransactions='00000')) ]
    cases = []
    for identity, overrides in variants:
        fields = {**baseline, **overrides}
        xml = '<GetAccountDetails>' + ''.join('<' + key + '>' + escape(value) + '</' + key + '>'
            for key, value in fields.items() if value is not None) + '</GetAccountDetails>'
        cases.append(BoundaryCase(case_id=identity, input_xml=xml, labels=['bank_request_seed_witness']))
    return cases


def response_cases():
    """Cross both runtime settings conditions with null, empty, whitespace and escaped values."""
    cases = []
    for channel_enabled in (False, True):
        for application_excluded in (False, True):
            for name, value in [('null', None), ('empty', ''), ('space', ' '), ('text', 'a&<b>"')]:
                identity = f'channel-{int(channel_enabled)}-excluded-{int(application_excluded)}-{name}'
                cases.append(BoundaryCase(case_id=identity, initial_context=dict(CHANNEL_NAME='InTeRnEt',
                    APPLICATION='BaNk', ErrorCategory='technical', ErrorNumber='42', ErrorDescription=value, RequestId='req'),
                    settings=[dict(**{'class': SETTINGS}, method='configure', arguments=[
                        ['internet'] if channel_enabled else [], ['bank'] if application_excluded else []])],
                    labels=['bank_response_seed_witness']))
    cases.append(BoundaryCase(case_id='unconfigured-settings', initial_context=dict(CHANNEL_NAME='INTERNET',
        APPLICATION='BANK', ErrorCategory=None, ErrorNumber='', ErrorDescription=None, RequestId='req')))
    return cases


# Each edit is single-site, preserves compilability and changes only the named behavior.
MUTATIONS = {
    'mandatory_removed': ('request_unformat', 'require(client); context.put("ClientId", client);',
        'context.put("ClientId", client);', 'client-empty', 'exception'),
    'null_to_zero_removed': ('request_unformat', 'if (maximum == null || maximum.isEmpty()) maximum = "0";',
        '/* seeded defect: null/empty conversion omitted */', 'maximum-empty', 'context.MaxTransactions'),
    'padding_wrong_side': ('request_unformat',
        'account.replaceFirst("^[" + java.util.regex.Pattern.quote("0") + "]+", "")',
        'account.replaceFirst("[" + java.util.regex.Pattern.quote("0") + "]+$", "")',
        'account-trailing-zero', 'context.AccountNumber'),
    'nil_always': ('response_format', 'boolean nil = channelEnabled && applicationAllowed && empty;',
        'boolean nil = true;', 'channel-0-excluded-0-text', 'output'),
    'nil_never': ('response_format', 'boolean nil = channelEnabled && applicationAllowed && empty;',
        'boolean nil = false;', 'channel-1-excluded-0-null', 'output'),
    'nil_channel_condition_removed': ('response_format', 'boolean nil = channelEnabled && applicationAllowed && empty;',
        'boolean nil = applicationAllowed && empty;', 'channel-0-excluded-0-null', 'output'),
    'nil_application_condition_removed': ('response_format', 'boolean nil = channelEnabled && applicationAllowed && empty;',
        'boolean nil = channelEnabled && empty;', 'channel-1-excluded-1-null', 'output'),
    'nil_empty_branch_removed': ('response_format', 'boolean empty = description == null || description.length() == 0;',
        'boolean empty = description == null;', 'channel-1-excluded-0-empty', 'output'),
    'nil_null_branch_removed': ('response_format', 'boolean empty = description == null || description.length() == 0;',
        'boolean empty = description != null && description.length() == 0;', 'channel-1-excluded-0-null', 'output'),
    'nil_prefix_changed': ('response_format',
        r'xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:nil=\"true\"',
        r'xmlns:wtc=\"http://www.w3.org/2001/XMLSchema-instance\" wtc:nil=\"true\"',
        'channel-1-excluded-0-null', 'output'),
}


def seed_defect(binding, name):
    """Fail loudly if a fixture changes instead of silently failing to plant a defect."""
    _, before, after, _, _ = MUTATIONS[name]
    changed = binding.model_copy(deep=True)
    assert changed.sources[0].content.count(before) == 1, name
    changed.sources[0].content = changed.sources[0].content.replace(before, after, 1)
    assert changed.sources[0].content != binding.sources[0].content
    return changed
