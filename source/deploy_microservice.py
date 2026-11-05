"""Explicit CLI for validated native microservice image/release actions."""
import argparse
import json
from pathlib import Path
from runtime.service_generation.deployment_configuration import read_deployment
from runtime.service_deployment.runner import execute_deployment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--values','--definition',dest='definition',required=True,help='Operation root values.yaml')
    parser.add_argument('--build-image',action='store_true')
    parser.add_argument('--demo-values',help='Explicit demo-values.yaml overlay; never selected implicitly')
    parser.add_argument('--publish-image',action='store_true')
    parser.add_argument('--deploy',action='store_true')
    args=parser.parse_args()
    overlays=[Path(args.demo_values).resolve()] if args.demo_values else []
    spec=read_deployment(args.definition,overlays=overlays)
    print(json.dumps(execute_deployment(args.project,spec,build=args.build_image,publish=args.publish_image,deploy=args.deploy,
        values_path=Path(args.definition).resolve(),**(dict(overlays=overlays) if overlays else {})),indent=2))


if __name__=='__main__':main()
