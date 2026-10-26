"""Select an explicitly configured production project for a consuming channel."""


def scoped_source_project(profile, channel):
    """Use an exact channel override, retaining the existing single-project fallback."""
    return (getattr(profile, 'scoped_java_projects', None) or {}).get(
        channel, getattr(profile, 'scoped_java_project', None))
