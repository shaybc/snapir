"""Create a separate facts-disabled test profile without starting or modifying a run."""
import argparse
from pathlib import Path
from models.pipeline_configuration import PipelineConfiguration


def create_profile(source, destination, output_root):
    """Copy settings into a fresh output namespace; preserve the source profile bytes."""
    source, destination, output_root = Path(source).resolve(), Path(destination).resolve(), Path(output_root).resolve()
    if source == destination or destination.exists():
        raise ValueError('Experimental profile must be a new file')
    before = source.read_bytes()
    profile = PipelineConfiguration.model_validate_json(before)
    original_root = Path(profile.output_root).resolve()
    if output_root == original_root or output_root.is_relative_to(original_root) or original_root.is_relative_to(output_root):
        raise ValueError('Experimental outputs must be separate from the existing run')
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError('Experimental output root must be new or empty')
    data = profile.model_dump(mode='json')
    data['output_root'] = str(output_root)
    data['executable_verification'].update(mode='conversion_checklist_v1', experimental_disable_facts=True)
    data['format_comparison'].update(enabled=True, collect_facts=False)
    data['metadata_checklist_batching'] = True  # Keep normal structural configuration valid; no mapping calls are made.
    data['staged_unit_conversion'] = True
    experimental = PipelineConfiguration.model_validate(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(experimental.model_dump_json(indent=2), encoding='utf-8')
    if source.read_bytes() != before:
        raise ValueError('Source profile changed during experiment setup')
    return experimental


def main(argv=None):
    """Write a profile only; deliberately has no conversion-run or monitoring entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args(argv)
    create_profile(args.source, args.destination, args.output_root)
    print('Experimental profile created. Conversion was not started.')


if __name__ == '__main__':
    main()
