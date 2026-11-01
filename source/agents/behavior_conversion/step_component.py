"""Source-driven instructions for reusable step implementations and individual occurrences."""


def step_instruction(kind):
    """Keep configuration and routing ownership distinct from reusable Java behavior."""
    if kind == 'step_implementation':
        return '''
Convert only this reusable operation-step implementation group and its supplied dependencies.
Translate initialization and context reads/writes to explicit typed configuration/state arguments.
Expose genuinely variable attributes and external collaborators as parameters; do not specialize
this shared implementation to one occurrence, channel, target operation or example value.
Preserve the original execute return code, exceptions and side-effect order. The configured
caller supplies resource providers or native operation clients; never recreate dynamic Composer
dispatch, service lookup or the enclosing operation's routing loop.
'''
    if kind == 'configured_step':
        return '''
Generate only the configured_unit occurrence, using its validated step implementation API.
The basic-component instruction about parameterized configuration applies to shared implementations;
this occurrence instead declares configuration_mode=specialized and cites its configuration evidence.
Supply an actual public int execute(...) entry method for its original integer outcome.
Initialize the supplied native implementation from this occurrence's exact XML attributes and
typed runtime inputs. Call its accepted methods; do not reimplement or copy its business logic.
Preserve all return outcomes, state writes, exceptions and external effects. Return the outcome
to the enclosing operation; do not choose the next step, execute siblings, or emit a routing loop.
Routes and return-format switches are evidence for composition, not instructions to run targets.
Use only this occurrence's operation_calls and service_connections. Complex calls use the saved
qualified native HTTP contract with injected deployment configuration; ordinary external resources
retain their evidenced provider, driver, ownership, errors and timeout behavior. No canned success.
Include tests proving this occurrence's actual configured values and outcome/side-effect behavior.
'''
    return ''
