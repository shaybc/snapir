"""Check single-source Helm values and fail-closed handling of old gate purposes."""
import sqlite3
import pytest
import yaml
from runtime.gate_numbering import check_gate_numbering
from runtime.service_generation.deployment_configuration import read_deployment,write_deployment
from tools.deployment_tools.helm_renderer import render_helm
from test_microservice_packaging import specification


def test_helm_uses_editable_operation_root_values_without_a_second_copy(tmp_path):
    operation=tmp_path/'operation';operation.mkdir()
    spec=specification();path=operation/'values.yaml';write_deployment(path,spec)
    path.write_text('# Reviewed settings\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
    before=path.read_bytes()
    raw=yaml.safe_load(before)
    assert raw['replicaCount']==1 and raw['service']['port']==8080
    assert raw['image']['baseImage']==spec.deployment.image.baseImage
    assert read_deployment(path)==spec
    project=tmp_path/'service';(project/'target').mkdir(parents=True)
    (project/'target/service.jar').write_bytes(b'fixture')
    old_chart=project/'helm/internet-example';old_chart.mkdir(parents=True)
    (old_chart/'values.yaml').write_text('stale: generated defaults')
    chart,_=render_helm(project,spec,values_path=path)
    assert path.read_bytes()==before
    assert not (chart/'values.yaml').exists() and not (project/'values.yaml').exists()
    raw['unexpected']='must not be discarded'
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError,match='Unsupported Helm values'):read_deployment(path)


@pytest.mark.parametrize('phase,old,new,header',[
    ('gate_4_pending','7_final_validation/gate_4_report.txt','6_service_generation_and_validation/gate_4_report.txt','=== Human Gate 4 ==='),
    ('gate_5_pending','6_service_generation_and_validation/gate_5_report.txt','7_final_validation/gate_5_report.txt','=== Human Gate 5: Create microservices ==='),
])
@pytest.mark.parametrize('moved',[False,True])
def test_old_numbered_gate_reports_never_authorize_a_new_purpose(tmp_path,phase,old,new,header,moved):
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
    path=tmp_path/'reports'/(new if moved else old);path.parent.mkdir(parents=True)
    path.write_text(header)
    with pytest.raises(ValueError,match='previous Gate 4/5 numbering'):
        check_gate_numbering(conn,'run',tmp_path,phase)
    current=tmp_path/'reports'/new;current.parent.mkdir(parents=True,exist_ok=True)
    current.write_text('=== Human Gate 4: Create microservices ===' if phase.startswith('gate_4') else '=== Human Gate 5 ===')
    check_gate_numbering(conn,'run',tmp_path,phase)
