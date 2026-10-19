"""Require isolated startup tests and deployment-owned JDBC driver configuration."""

import re

from runtime.java_public_type import _code
from runtime.behavior_conversion.method_contracts import java_type_resolver
from tools.validation_tools.java_comments import mask_java_comments

STARTUP_EXAMPLE = '''Startup wiring test pattern (adapt names and types to the actual contract):
try (var context = new AnnotationConfigApplicationContext()) {
    context.addBeanFactoryPostProcessor(factory -> {
        factory.registerSingleton("dataSource", Mockito.mock(DataSource.class));
        factory.registerSingleton("externalClient", Mockito.mock(ExternalClient.class));
    });
    context.register(ProductionConfiguration.class);
    context.refresh();
    var service = context.getBean(OperationService.class);
    assertFalse(Mockito.mockingDetails(service).isMock());
    var step = context.getBean("configuredStepRole", AcceptedStep.class);
    assertFalse(Mockito.mockingDetails(step).isMock());
    // Check each configured role is the same bean stored in the service.
}
Register substitutes under the actual production bean names BEFORE refresh, so production
external-resource factories never run. Keep every operation and step bean real. Include
all external resource/client beans needed to start the configuration, not only JDBC.
Tests must not supply real credentials, drivers, database servers or network endpoints.'''


def validate_startup_substitutes(files, contract):
    """Require an isolated startup test for each contracted external provider type."""
    resources = [item['provider_type'] for item in contract.get('runtime_resources', [])]
    if not resources:
        return
    for path, source in files.items():
        if not path.startswith('src/test/java/'):
            continue
        code = _code(source)
        if 'AnnotationConfigApplicationContext' not in code or '.getBean(' not in code:
            continue
        resolve = java_type_resolver(source, resources)
        mocked = {resolve(match[1]) for match in re.finditer(
            r'\bmock\s*\(\s*([\w.$]+)\s*\.\s*class\s*\)', code)}
        missing = set(resources) - mocked
        registration = re.search(r'\b(?:registerSingleton|registerBean)\s*\(', code)
        refresh = re.search(r'\.\s*refresh\s*\(', code)
        deferred = re.search(r'\bnew\s+(?:[\w.]+\.)?AnnotationConfigApplicationContext\s*\(\s*\)', code)
        if not missing and registration and refresh and deferred and registration.start() < refresh.start():
            return
    raise ValueError('Startup wiring test must register mocks for external providers before Spring refresh: '
                     + ', '.join(resources) + '. Test the real service and step beans; do not run production resource factories. '
                     + STARTUP_EXAMPLE)


def validate_jdbc_driver(files, dependencies):
    """Require deployment driver selection and a verified production-scope class owner."""
    properties = '\n'.join(content for path, content in files.items() if path.endswith('application.properties'))
    java = '\n'.join(mask_java_comments(content) for path, content in files.items() if path.startswith('src/main/java/'))
    hardcoded = re.findall(r'\bsetDriverClassName\s*\(\s*"([^"\\]+)"\s*\)', java)
    if hardcoded:
        raise ValueError('Production JDBC driver must come from deployment settings, not setDriverClassName literals: '
                         + ', '.join(sorted(set(hardcoded)))
                         + '. Bind spring.datasource.driver-class-name to an environment placeholder and declare its driver class in a verified compile/runtime dependency.')
    setting = re.search(r'(?m)^\s*spring\.datasource\.driver-class-name\s*=\s*([^\r\n]+)', properties)
    if not setting:
        return  # URL-based JDBC auto-detection remains supported.
    value = setting[1].strip()
    placeholder = re.fullmatch(r'\$\{[^}:]+(?::([^}]+))?\}', value)
    if not placeholder:
        raise ValueError('Production JDBC driver-class-name must use a deployment environment placeholder, not a fixed vendor.')
    default = placeholder[1]
    if default and not any(default in dependency.required_classes and dependency.scope in {'compile', 'runtime'}
                           for dependency in dependencies):
        raise ValueError('Configured JDBC driver class ' + default + ' has no verified compile/runtime dependency declaration. '
                         'Declare the resolved artifact containing this class with its known version and required_classes; '
                         'a Spring JDBC starter does not supply a database vendor driver. Do not invent a driver or version.')
