"""Maintain and stage converter fixture JDBC tools; never starts an operation conversion."""
import argparse
import json
from runtime.fixture_jdbc_tools.releases import default_store, locate_release, digest
from runtime.fixture_jdbc_tools.staging import stage_release


def main(argv=None):
    """Separate explicit compilation/publication from read-only lookup and exact staging."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('build-release', 'verify-release', 'stage'):
        command = commands.add_parser(name)
        command.add_argument('--store', default=str(default_store()))
        if name == 'build-release':
            command.add_argument('--version', required=True)
            command.add_argument('--work')
            command.add_argument('--java-home')
            command.add_argument('--maven-settings')
            command.add_argument('--maven-repository')
        else:
            command.add_argument('--bundle', required=True)
        if name == 'stage':
            command.add_argument('--destination', required=True)
    args = parser.parse_args(argv)
    if args.command == 'build-release':
        from runtime.fixture_jdbc_tools.build import build_release
        result = build_release(args.version, store=args.store, work=args.work, java_home=args.java_home,
            maven_settings=args.maven_settings, maven_repository=args.maven_repository)
    elif args.command == 'stage':
        result = stage_release(args.bundle, args.destination, args.store)
    else:
        directory, release = locate_release(args.bundle, args.store)
        result = dict(root=str(directory), bundle_id=release.bundle_id, manifest_hash=digest(release.model_dump(mode='json')))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
