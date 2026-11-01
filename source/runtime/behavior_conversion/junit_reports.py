"""Read executed JUnit cases without confusing nested/display-named suites with classes."""
from xml.etree import ElementTree


def execution_evidence(paths):
    """Count cases once across reports; aggregate suite counters are not extra tests."""
    cases, classes, issues = {}, set(), []
    for path in sorted(paths):
        root = ElementTree.parse(path).getroot()
        owner = path.stem.removeprefix('TEST-')
        suites = list(root.iter('testsuite'))
        failed = any(int(s.get('failures', '0')) or int(s.get('errors', '0')) for s in [root, *suites])
        failed = failed or next(root.iter('failure'), None) is not None or next(root.iter('error'), None) is not None
        if failed:
            issues.append('Failed behavioral tests: ' + path.name)
        entries = list(root.iter('testcase'))
        occurrences = {}
        for case in entries:
            name = case.get('classname') or owner
            identity = (name, case.get('name', ''))
            occurrences[identity] = occurrences.get(identity, 0) + 1
            key = (*identity, occurrences[identity])
            executed = case.find('skipped') is None
            cases[key] = cases.get(key, False) or executed
            if executed:
                classes.update((name, owner))
        if not entries:
            # Old receipts/fixtures can contain counters only. Use leaf suites so a
            # testsuites wrapper or aggregate parent cannot double the execution count.
            for suite in suites:
                if suite.findall('testsuite'):
                    continue
                count = max(0, int(suite.get('tests', '0')) - int(suite.get('skipped', '0')))
                name = suite.get('name') or owner
                for index in range(count):
                    cases.setdefault((name, '#counter-' + str(index)), True)
                if count:
                    classes.update((name, owner))
    return sum(cases.values()), sorted(classes), issues
