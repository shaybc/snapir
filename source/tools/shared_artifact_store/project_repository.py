"""Make generated-library resolution portable without replacing user Maven settings."""
from pathlib import Path
from xml.etree import ElementTree


def attach_repository(pom_path, dependencies, *, retained=False):
    """Add a relative repository only when the project consumes approved generated components."""
    if not retained and not any(getattr(item, 'group_id', None) == 'il.co.dcd.converted' for item in dependencies):
        return
    identifier = 'approved-retained-libraries' if retained else 'approved-converted-components'
    url = 'file://${project.basedir}/' + ('retained-dependencies' if retained else 'shared-dependencies') + '/repository'
    from tools.maven_dependency_tools.pom_manager import project_lock
    with project_lock(Path(pom_path)):
        tree = ElementTree.parse(pom_path)
        root = tree.getroot()
        namespace = root.tag.partition('}')[0] + '}' if '}' in root.tag else ''
        if namespace:
            ElementTree.register_namespace('', namespace[1:-1])
        repositories = root.find(namespace + 'repositories')
        if repositories is None:
            repositories = ElementTree.SubElement(root, namespace + 'repositories')
        for item in repositories:
            if item.findtext(namespace + 'id') == identifier:
                if item.findtext(namespace + 'url') != url:
                    raise ValueError('Generated component repository must use its portable relative URL')
                return
        repository = ElementTree.SubElement(repositories, namespace + 'repository')
        ElementTree.SubElement(repository, namespace + 'id').text = identifier
        ElementTree.SubElement(repository, namespace + 'url').text = url
        tree.write(pom_path, encoding='utf-8', xml_declaration=True)
