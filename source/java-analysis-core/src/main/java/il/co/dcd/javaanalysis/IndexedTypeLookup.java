package il.co.dcd.javaanalysis;

import java.sql.*;
import java.util.*;

/** Canonical project visibility over bounded indexed SQL lookups, shared by both launch paths. */
public final class IndexedTypeLookup implements TypeLookup,AutoCloseable {
    private final Connection connection;
    private final Map<String,PreparedStatement> statements=new LinkedHashMap<>(32,0.75f,true);
    private boolean overrideOwner;private String ownerPath,ownerProject;
    public IndexedTypeLookup(Connection connection)throws SQLException {
        this.connection=connection;
        try(var statement=connection.createStatement()){statement.execute("CREATE TEMP TABLE IF NOT EXISTS reference_lookup_names(name TEXT PRIMARY KEY)");}
    }
    public void owner(String path,boolean override,String project){ownerPath=path;overrideOwner=override;ownerProject=project;}
    private PreparedStatement statement(String sql,Object...arguments)throws SQLException {
        var statement=statements.get(sql);
        if(statement==null){if(statements.size()>=32){var oldest=statements.entrySet().iterator();oldest.next().getValue().close();oldest.remove();}statement=connection.prepareStatement(sql);statements.put(sql,statement);}
        statement.clearParameters();for(int i=0;i<arguments.length;i++)statement.setObject(i+1,arguments[i]);return statement;
    }
    private String scalar(String sql,Object...arguments){try(var rows=statement(sql,arguments).executeQuery()){return rows.next()?rows.getString(1):null;}catch(SQLException error){throw new IllegalStateException(sql,error);}}
    private void execute(String sql,Object...arguments){try{statement(sql,arguments).executeUpdate();}catch(SQLException error){throw new IllegalStateException(sql,error);}}
    public boolean contains(String fqcn){return scalar("SELECT fqcn FROM java_sources WHERE fqcn=? LIMIT 1",fqcn)!=null;}
    private void names(Set<String> names){execute("DELETE FROM reference_lookup_names");for(String name:names)execute("INSERT INTO reference_lookup_names VALUES (?)",name);}
    public List<String> eligible(Set<String> names,String source) {
        if(names.isEmpty())return List.of();names(names);
        String owner=overrideOwner&&source.equals(ownerPath)?ownerProject:scalar("SELECT project FROM java_sources WHERE file=? LIMIT 1",source);
        String clause="fqcn IN (SELECT name FROM reference_lookup_names)";Object[] arguments={};
        if(scalar("SELECT file FROM java_sources WHERE "+clause+" AND project IS ? LIMIT 1",owner)!=null){clause+=" AND project IS ?";arguments=new Object[]{owner};}
        else if("1".equals(scalar("SELECT declared FROM java_projects WHERE name=?",owner))) {
            clause+=" AND project IN (WITH RECURSIVE allowed(name) AS (SELECT ? UNION SELECT r.target FROM java_project_refs r JOIN allowed a ON r.project=a.name) SELECT name FROM allowed)";
            arguments=new Object[]{owner};
        }
        var result=new ArrayList<String>();
        try(var rows=statement("SELECT DISTINCT file FROM java_sources WHERE "+clause+" ORDER BY file LIMIT 2",arguments).executeQuery()){while(rows.next())result.add(rows.getString(1));}
        catch(SQLException error){throw new IllegalStateException("Source visibility lookup failed",error);}return result;
    }
    public boolean existsOutsideVisibility(Set<String> names,String source){if(names.isEmpty())return false;names(names);return scalar("SELECT file FROM java_sources WHERE fqcn IN (SELECT name FROM reference_lookup_names) LIMIT 1")!=null;}
    public void close(){for(var statement:statements.values())try{statement.close();}catch(SQLException error){throw new IllegalStateException(error);}statements.clear();}
}
