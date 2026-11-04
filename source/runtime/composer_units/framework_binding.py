"""Describe supported original framework interfaces and preflight their actual public APIs."""
from xml.etree import ElementTree as ET
from runtime.java_toolchain import run_java
from tools.behavior_verification.boundary_contracts import _format_entry
import os


def resolve(spec,unit):
    """Select interface families, never individual formatter/decorator class names."""
    binding=spec.framework.model_copy(deep=True)
    binding.adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'
    binding.original_action=None
    if spec.kind=='decorator':
        binding.adapter_class='il.co.dcd.verification.harness.LegacyDecoratorAdapter'
        binding.original_action={'decorate':'addDecoration','undecorate':'removeDecoration','format_attributes':'formatXmlAttributes'}[spec.action]
    return binding


def preflight(spec,unit,binding,compiled,path):
    """Reflect over compiled source/JAR APIs without constructing or initializing business objects."""
    job=ET.Element('preflight',context=binding.context_class,tag=binding.tag_class,writer=binding.context_writer,
        snapshot=binding.context_snapshot,owner=_format_entry(unit),action=binding.original_action or spec.action)
    from tools.behavior_verification.boundary_protocol import configuration_element
    configuration=ET.SubElement(job,'configuration')
    configuration.append(configuration_element(unit['effective_configuration'],{d['definition_id']:d for d in unit.get('referenced_definitions',[])}))
    def visit(node):
        if node.get('java_class'):
            item=ET.SubElement(job,'type',name=node['java_class'])
            for key in node.get('attributes',{}):ET.SubElement(item,'attribute',name=key)
        for child in [*node.get('children',[]),*node.get('decorators',[])]:visit(child)
    for node in [unit['effective_configuration'],*unit.get('referenced_definitions',[])]:visit(node)
    ET.ElementTree(job).write(path,encoding='utf-8')
    result=run_java(['java','-cp',os.pathsep.join(compiled['classpath']),'il.co.dcd.verification.harness.LegacyUnitPreflight',str(path)],capture_output=True,text=True,timeout=60,check=False)
    if result.returncode:raise ValueError('Unsupported original initialization/invocation contract: '+result.stderr[-2500:])
