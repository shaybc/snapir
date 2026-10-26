"""Recognize indexed JDK packages while retaining full syntax dependency validation."""


def verified_platform_wildcard(name, source_index, classpath):
    """Prove the import names a JDK package with no competing visible type origins.

    This proves package availability only. Every actual type use must still pass
    check_scoped_java_dependencies; it does not grant wildcard imports a type bypass.
    """
    if not name.endswith('.*'):
        return False
    package = name[:-2]
    matches = {fqcn: origins for fqcn, origins in classpath.classes.items()
               if fqcn.rsplit('.', 1)[0] == package}
    if not matches or any(len(origins) != 1 or not origins[0].startswith('jdk:') for origins in matches.values()):
        return False
    return not any(fqcn.rsplit('.', 1)[0] == package for fqcn in source_index.classes)
