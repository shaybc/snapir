"""Generate single-site native mutations with the existing pinned JavaParser tool."""
from xml.etree import ElementTree as ET
from runtime.java_toolchain import run_java


def generate_mutations(binding,tool,directory,limit,owned_paths=None):
    """Persist mutated source plans; never write to supplied source files or the candidate."""
    root=ET.Element('sources',limit=str(limit))
    for file in binding.sources:
        if file.path.startswith('src/test/'):continue
        if owned_paths is not None and file.path not in owned_paths:continue
        ET.SubElement(root,'file',path=file.path).text=file.content
    source=directory/'mutation-input.xml';output=directory/'mutation-plans.xml'
    ET.ElementTree(root).write(source,encoding='utf-8',xml_declaration=True)
    result=run_java(['java','-cp',str(tool),'il.co.dcd.verification.ComparisonMutations',str(source),str(output)],
        capture_output=True,text=True,timeout=90,check=False)
    if result.returncode:raise ValueError('Mutation parser failed: '+result.stderr[-2000:])
    return [dict(node.attrib,content=node.text) for node in ET.parse(output).getroot().findall('mutation')]
