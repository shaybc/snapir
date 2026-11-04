"""Exercise generic stored-procedure outputs without a database or business-class mocks."""
import os
from test_shared_fixture_execution import boundary_tool, jdk
from runtime.java_toolchain import run_java
import pytest
from models.shared_test_fixture import SharedFixtureBank
from runtime.test_assets.validation import validate_bank


@pytest.mark.parametrize('outputs',[
    {'0':{'sql_type':12,'value':'OK'}},
    {'2':{'sql_type':'VARCHAR','value':'OK'}},
    {'2':{'sql_type':12}},
    {'2':{'sql_type':12,'value':'OK','rows':[]}},
    {'3':{'sql_type':2012,'columns':['VALUE'],'rows':[['one','two']]}}
])
def test_callable_fixture_schema_rejects_invalid_outputs(outputs):
    bank=SharedFixtureBank(fixtures={'db':dict(kind='database',value={'queries':[
        dict(sql='{call SAMPLE(?)}',parameters=[],out_parameters=outputs)]})})
    with pytest.raises(ValueError):validate_bank(bank,[],10000)


def test_callable_fixture_outputs_cursor_errors_and_registration(boundary_tool, tmp_path):
    code = '''import java.sql.*;import java.util.*;
import il.co.dcd.verification.fixtures.*;
public class CallableFixtureTest {
 static Connection connection(String status,List<List<String>> rows,boolean failure){
  Map<String,Object> query=new HashMap<>();query.put("sql","{call SAMPLE(?,?,?)}");query.put("parameters",List.of("key"));
  query.put("out_parameters",Map.of("2",Map.of("sql_type",Types.VARCHAR,"value",status),
   "3",Map.of("sql_type",Types.REF_CURSOR,"columns",List.of("VALUE"),"rows",rows)));
  if(failure)query.put("exception",Map.of("message","database failure"));
  return JdbcFixtureProvider.connection(Map.of("queries",List.of(query)),new ArrayList<>());
 }
 static CallableStatement call(Connection connection)throws Exception{
  var call=connection.prepareCall("{call SAMPLE(?,?,?)}");call.setString(1,"key");
  call.registerOutParameter(2,Types.VARCHAR);call.registerOutParameter(3,Types.REF_CURSOR);return call;
 }
 public static void main(String[] args)throws Exception{
  try(var c=connection("OK",List.of(List.of("first"),List.of("second")),false);var s=call(c)){
   if(s.execute()||!"OK".equals(s.getString(2)))throw new AssertionError("status");
   try(var rows=(ResultSet)s.getObject(3)){
    if(!rows.next()||!"first".equals(rows.getString("VALUE"))||!rows.next()||!"second".equals(rows.getString(1))||rows.next())throw new AssertionError("cursor");
   }
  }
  try(var c=connection("NOT_FOUND",List.of(),false);var s=call(c)){
   s.execute();try(var rows=(ResultSet)s.getObject(3)){if(rows.next())throw new AssertionError("empty");}
  }
  try(var c=connection("ERROR",List.of(),true);var s=call(c)){
   try{s.execute();throw new AssertionError("failure missing");}catch(SQLException expected){if(!"database failure".equals(expected.getMessage()))throw expected;}
  }
  try(var c=connection("OK",List.of(),false);var s=call(c)){
   s.registerOutParameter(3,Types.INTEGER);
   try{s.execute();throw new AssertionError("registration mismatch hidden");}catch(il.co.dcd.verification.harness.BoundaryRuntime.Incomplete expected){}
  }
  try(var c=connection("OK",List.of(),false);var s=call(c)){
   s.setString(1,"wrong");
   try{s.execute();throw new AssertionError("parameter mismatch hidden");}catch(il.co.dcd.verification.harness.BoundaryRuntime.Incomplete expected){}
  }
 }
}'''
    source=tmp_path/'CallableFixtureTest.java';source.write_text(code)
    compiled=run_java(['javac','-cp',str(boundary_tool),str(source)],capture_output=True,text=True,timeout=60,check=False)
    assert compiled.returncode==0,compiled.stderr
    executed=run_java(['java','-ea','-cp',os.pathsep.join([str(tmp_path),str(boundary_tool)]),'CallableFixtureTest'],capture_output=True,text=True,timeout=60,check=False)
    assert executed.returncode==0,executed.stderr
