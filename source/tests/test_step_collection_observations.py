"""Paired stored-procedure steps observe typed DTO rows through explicit public getters."""
from test_shared_fixture_execution import boundary_tool,jdk
from test_behavior_verification_boundaries import source,unit
from test_format_comparison_execution import demo_sources
from models.shared_test_fixture import SharedFixtureBank
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.native_unit_bundle import NativeSourceFile
from models.pipeline_configuration import PipelineConfiguration
from runtime.test_assets.materialization import comparison_plan
from runtime.step_comparison.runner import run_step_comparison


def test_step_callable_results_project_actual_rows_and_preserve_absence(boundary_tool,tmp_path):
    original='''package example;import com.ibm.dse.base.*;import java.sql.*;import java.util.*;
public class Step {private Context context;public void setContext(Context c){context=c;}
public int execute()throws Exception{
try(var s=context.getConnection().prepareCall("{call SAMPLE(?,?,?)}")){
s.setString(1,(String)context.getValueAt("Key"));s.registerOutParameter(2,Types.VARCHAR);s.registerOutParameter(3,Types.REF_CURSOR);s.execute();
List<Map<String,Object>> values=new ArrayList<>();try(var r=(ResultSet)s.getObject(3)){
while(r.next()){Map<String,Object> row=new LinkedHashMap<>();row.put("Id",r.getString("ID"));row.put("Enabled","Y".equals(r.getString("ENABLED")));values.add(row);}}
if(values.isEmpty())return 4;context.setValueAt("Rows",values);return 0;
}catch(SQLException e){context.setValueAt("Error",e.getMessage());return 8;}}}'''
    native='''package nativecode;import java.sql.*;import java.util.*;
public class Step {private List<Row> rows;private String error;
public boolean hasRows(){return rows!=null;}public boolean hasError(){return error!=null;}
public List<Row> getRows(){return rows;}public String getError(){return error;}
public int execute(Connection connection,String key)throws Exception{
try(var s=connection.prepareCall("{call SAMPLE(?,?,?)}")){
s.setString(1,key);s.registerOutParameter(2,Types.VARCHAR);s.registerOutParameter(3,Types.REF_CURSOR);s.execute();
List<Row> values=new ArrayList<>();try(var r=(ResultSet)s.getObject(3)){while(r.next())values.add(new Row(r.getString("ID"),"Y".equals(r.getString("ENABLED"))));}
if(values.isEmpty())return 4;rows=values;return 0;
}catch(SQLException e){error=e.getMessage();return 8;}}}'''
    dto='package nativecode;public class Row {private String id;private boolean enabled;public Row(String id,boolean enabled){this.id=id;this.enabled=enabled;}public String getId(){return id;}public boolean isEnabled(){return enabled;}}'
    fixtures={'key':dict(value='fixture-key')};scenarios=[]
    for label,rows,failure in [('rows',[['first','Y'],['second','N']],None),('empty',[],None),('error',[],dict(type='java.sql.SQLException',message='fixture failure'))]:
        query=dict(sql='{call SAMPLE(?,?,?)}',parameters=['fixture-key'],out_parameters={'2':dict(sql_type=12,value='OK'),'3':dict(sql_type=2012,columns=['ID','ENABLED'],rows=rows)})
        if failure:query['exception']=failure
        fixtures[label]=dict(kind='database',value=dict(queries=[query]))
        scenarios.append(dict(scenario_id=label,purpose='Actual result state',direction='step_execute',
            resources={'db':dict(fixture_id=label)},composer_resource_setters={'setConnection':'db'},
            inputs={'key':dict(fixture_id='key')},composer_context={'Key':dict(fixture_id='key')},observe_context_keys=['Rows','Error'],
            native_entry=dict(owner_type='nativecode.Step',method_name='execute',arguments=[dict(type_name='java.sql.Connection',source='resource',key='db'),dict(type_name='java.lang.String',source='fixture',key='key')],
                context_writes=[dict(context_key='Rows',source='receiver',getters=['getRows'],presence_getters=['hasRows'],collection_fields={'Id':['getId'],'Enabled':['isEnabled']}),
                    dict(context_key='Error',source='receiver',getters=['getError'],presence_getters=['hasError'])])))
    original_unit=unit('configured_step','example.Step',sources=[*demo_sources(),source('step',original)])
    plan=comparison_plan('step',original_unit,[NativeSourceFile(path='src/main/java/nativecode/Step.java',content=native),NativeSourceFile(path='src/main/java/nativecode/Row.java',content=dto)],SharedFixtureBank(fixtures=fixtures),ComparisonScenarioSuite(scenarios=scenarios),'step-manifest')
    report=run_step_comparison(plan,PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False}),tmp_path/'paired',tool=boundary_tool)
    assert report['counts']['matched']==3,report
    assert report['cases'][0]['native']['context']['Rows']==[{'Id':'first','Enabled':True},{'Id':'second','Enabled':False}]
    assert 'Rows' not in report['cases'][1]['native']['context']
    assert report['cases'][2]['native']['context']['Error']=='fixture failure'
