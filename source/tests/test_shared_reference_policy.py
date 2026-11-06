"""Compare the shared resolver with the frozen converter policy on raw reference facts."""

from xml.etree import ElementTree as ET
import pytest
from models.java_source_index import JavaSourceIndex
from tests.java_resolution_oracle import resolve_reference as previous_policy
from tools.java_analysis_tools.source_dependencies.resolution import resolve_reference


@pytest.mark.parametrize('visible',[False,True])
def test_shared_policy_matches_original_resolution_and_ambiguity(tmp_path,visible):
    paths={name:str(tmp_path/project/'src'/relative) for name,project,relative in (
        ('step','P','p/Step.java'),('helper','C','lib/Helper.java'),('hidden','X','hidden/Secret.java'),
        ('duplicate','X','lib/Helper.java'),('leaf','C','lib/Leaf.java'),('roman','P','p/Ⅻ.java'))}
    classes={'p.Step':[paths['step']],'lib.Helper':[paths['helper'],paths['duplicate']],
        'lib.Leaf':[paths['leaf']],'hidden.Secret':[paths['hidden']],'p.Ⅻ':[paths['roman']]}
    projects={path:('P' if key in {'step','roman'} else 'C' if key in {'helper','leaf'} else 'X') for key,path in paths.items()}
    index=JavaSourceIndex(workspace_root=str(tmp_path),classes=classes,class_projects=projects,
        source_roots={project:[str(tmp_path/project/'src')] for project in ('P','C','X')},
        project_references={'P':['C','X'] if visible else ['C'],'C':[],'X':[]})
    document=ET.Element('source',path=paths['step'],package='p')
    for name,static in [('lib.*','false'),('lib.Helper.value','true')]:ET.SubElement(document,'import',name=name,static=static)
    for kind,name in [('variable','helper'),('local_type','Local'),('type_parameter','T'),('method','mine')]:ET.SubElement(document,kind,name=name)
    references=[]
    for kind,name in [('type','Helper'),('type','lib.Helper.Inner'),('type','hidden.Secret'),('type','Leaf'),
        ('type','Ⅻ'),('type','T'),('type','Local'),('qualifier','helper.value'),('static_member','value'),
        ('static_member','mine'),('static_field','missing'),('type','java.lang.String'),('qualifier','this.value')]:
        references.append(ET.SubElement(document,'reference',name=name,kind=kind,offset=str(len(references))))
    for reference in references:
        assert resolve_reference(reference,document,index,paths['step'])==previous_policy(reference,document,index,paths['step'])
