"""Single-command original Composer format/decorator preparation and execution."""
import argparse,json,sqlite3
from pathlib import Path
from models.composer_unit_specification import ComposerUnitSpecification
from runtime.configuration import load_configuration
from runtime.composer_units.selection import select_format,standalone,select_element
from runtime.composer_units.packaging import prepare
from runtime.composer_units.execution import execute


def _main(argv=None):
    """Read scoped Mapper state only; never initialize or resume conversion tasks."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run']);parser.add_argument('--profile',required=True)
    parser.add_argument('--kind',choices=['format','decorator'],default='format')
    parser.add_argument('--action',choices=['format','unformat','decorate','undecorate','format_attributes'])
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--unit');source.add_argument('--definition');source.add_argument('--class',dest='owner')
    source.add_argument('--package')
    for name in ['state-db','run-id','channel','operation','configuration','framework','scenario','selector']:parser.add_argument('--'+name)
    parser.add_argument('--cache');parser.add_argument('--output',required=True)
    args=parser.parse_args(argv);profile=load_configuration(args.profile)
    if args.package:
        if args.command!='run' or not args.scenario:parser.error('Prepared package execution requires run and scenario')
        from runtime.composer_units.cache import verify
        verify(args.package)
        spec=json.loads((Path(args.package)/'specification.json').read_text())
        if args.action and args.action!=spec['action']:parser.error('Action differs from prepared package')
        result=execute(args.package,json.loads(Path(args.scenario).read_text()),profile,args.output)
        print(result.model_dump_json());return 0 if result.status=='execution_completed' else 2
    if not args.action:parser.error('Preparation needs an action')
    if not args.cache:parser.error('Preparation needs a cache directory')
    if args.unit:unit=json.loads(Path(args.unit).read_text(encoding='utf-8'))
    elif args.definition:
        if not all([args.state_db,args.run_id,args.channel,args.operation]):parser.error('Definition needs qualified state-db, run-id, channel and operation')
        conn=sqlite3.connect('file:'+Path(args.state_db).resolve().as_posix()+'?mode=ro',uri=True)
        try:unit=select_format(conn,args.run_id,args.channel,args.operation,args.definition,profile.source_root)
        finally:conn.close()
    else:
        attributes={}
        if args.configuration:
            raw=Path(args.configuration).read_text(encoding='utf-8-sig')
            if raw.lstrip().startswith('<'):
                from xml.etree import ElementTree as ET
                tag=ET.fromstring(raw)
                if list(tag):raise ValueError('Configured children need qualified Mapper selection, not an unmapped XML tag')
                attributes=dict(tag.attrib)
            else:attributes=json.loads(raw)
        unit=standalone(args.owner,attributes)
        if args.configuration:
            from runtime.composer_units.cache import file_hash
            unit['configuration_revisions']={str(Path(args.configuration).resolve()):file_hash(args.configuration)}
    if args.selector:unit=select_element(unit,args.selector)
    data=dict(kind=args.kind,action=args.action,unit=unit)
    if args.scenario:
        from models.boundary_case import BoundaryCase
        scenario=BoundaryCase.model_validate_json(Path(args.scenario).read_text())
        types=set()
        def visit(recipe):
            if recipe.source=='object':types.add(recipe.type_name)
            for child in [*recipe.arguments,*recipe.properties.values()]:visit(child)
            if recipe.element:visit(recipe.element)
        for recipe in scenario.original_inputs.values():visit(recipe)
        data['input_types']=sorted(types)
    if args.framework:data['framework']=json.loads(Path(args.framework).read_text())
    result=prepare(ComposerUnitSpecification.model_validate(data),profile,args.cache)
    if args.command=='run' and result.status=='package_ready':
        if not args.scenario:parser.error('Run requires a scenario file')
        result=execute(result.package,json.loads(Path(args.scenario).read_text()),profile,args.output)
    else:
        output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
        (output/'result.json').write_text(result.model_dump_json(indent=2))
    print(result.model_dump_json())
    return 0 if result.status in {'package_ready','execution_completed'} else 2


def main(argv=None):
    """Report unavailable preparation as structured output, without conversion state writes."""
    from models.composer_unit_result import ComposerUnitResult
    try:return _main(argv)
    except (ValueError,OSError,RuntimeError) as error:
        print(ComposerUnitResult(status='preparation_unavailable',issues=[str(error)]).model_dump_json());return 2


if __name__=='__main__':raise SystemExit(main())
