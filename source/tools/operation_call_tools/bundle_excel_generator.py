"""Rebuild the portable Excel reader from canonical source modules deterministically."""

import ast
from pathlib import Path

MODULES = (
    'composer_mapper_tools/frontmatter_parser.py','composer_mapper_tools/operation_parser.py',
    'composer_mapper_tools/opstep_parser.py','composer_mapper_tools/channel_registry_parser.py',
    'composer_mapper_tools/manifest_json_stream.py','operation_call_tools/export_progress.py',
    'composer_mapper_tools/indexed_analysis.py','composer_mapper_tools/indexed_operation_calls.py',
    'operation_call_tools/indexed_waves.py','operation_call_tools/streamed_workbook.py','operation_call_tools/indexed_export.py',
    'composer_mapper_tools/vault_manifest.py','operation_call_tools/discovery.py','operation_call_tools/ordering.py',
)


def bundle(root):
    """Preserve the standalone workbook UI and replace only its shared reader snapshots."""
    destination=root/'Excel Generator.py'
    prefix=destination.read_text(encoding='utf-8-sig').split('# Bundled from ',1)[0]
    parts=[prefix]
    exports={}
    for relative in MODULES:
        source=ast.parse((root/'source/tools'/relative).read_text(encoding='utf-8-sig'))
        source.body=[node for node in source.body if not isinstance(node,ast.ImportFrom) or not (node.module or '').startswith(('tools.','models.','__future__'))]
        exports['tools.'+relative[:-3].replace('/','.')] = [node.name for node in source.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))]
        parts.append('# Bundled from source/tools/'+relative+'\n'+ast.unparse(source)+'\n\n')
    parts.append('''# Standalone readers use the same function bodies, including their lazy imports.
import types
def current_mapped(workspace=None):
    return None
''')
    exports['tools.composer_mapper_tools.mapped_scope']=['current_mapped']
    parts.append('import importlib.util\n'
                 'try:\n'
                 '    _standalone = importlib.util.find_spec("tools.composer_mapper_tools") is None\n'
                 'except (ModuleNotFoundError, ValueError):\n'
                 '    _standalone = True\n'
                 'if _standalone:\n'
                 '    for _module_name, _exports in '+repr(exports)+'.items():\n'
                 '        _module = types.ModuleType(_module_name)\n'
                 '        _module.__dict__.update({name: globals()[name] for name in _exports})\n'
                 '        sys.modules[_module_name] = _module\n')
    parts.append("\nif __name__ == '__main__':\n    raise SystemExit(main())\n")
    destination.write_text(''.join(parts),encoding='utf-8')


if __name__=='__main__':
    bundle(Path(__file__).resolve().parents[3])
