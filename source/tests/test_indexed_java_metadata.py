"""Protect the mapper's documentary Java fields alongside modern source forms."""

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,workspace
from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis


def test_shared_ast_preserves_mapper_metadata_and_non_class_units(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source');folder=root/'src/pkg'
    (folder/'Step.java').write_text('''package pkg;
import java.sql.Connection;
import com.ibm.External;
/** Returns 0 (success), 4 (missing client) */
public class Step extends Helper implements java.io.Serializable {
 private static final int OK=0;
 private String clientId;
 public Step() {}
 public void setClientId(String value) { clientId=value; }
 public int execute() throws java.sql.SQLException {
   if(clientId==null) throw new IllegalArgumentException("client");
   if(clientId.isEmpty()) return 4;
   return OK;
 }
}''')
    (folder/'Unrelated.java').write_text('package pkg; public record Unrelated(int value) {}')
    (folder/'Kind.java').write_text('package pkg; public enum Kind { A,B }')
    (folder/'Marker.java').write_text('package pkg; public @interface Marker {}')
    (folder/'package-info.java').write_text('/** Package documentation. */ package pkg;')
    (folder/'Empty.java').write_text('')
    (folder/'Commented.java').write_text('// package wrong; class Commented {}\n/* all inactive */')
    vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    with IndexedAnalysis(vault) as analysis:
        conn=analysis.conn;file=str(folder/'Step.java')
        facts={}
        for kind,name in conn.execute("SELECT kind,name FROM java_facts WHERE file=? AND kind LIKE 'metadata:%'",(file,)):
            facts.setdefault(kind,set()).add(name)
        assert facts['metadata:method']>={'Step','setClientId','execute'}
        assert facts['metadata:setter']=={'setClientId'}
        assert facts['metadata:interface']=={'java.io.Serializable'}
        assert facts['metadata:exception']>={'java.sql.SQLException','IllegalArgumentException'}
        assert facts['metadata:external']=={'IBM/WAS','Database'}
        assert facts['metadata:behavior']=={'db_accessor'}
        assert set(conn.execute("SELECT name,value FROM java_facts WHERE file=? AND kind='metadata:return'",(file,)))>={('0','success'),('4','missing client')}
        assert conn.execute('SELECT parent FROM java_classes WHERE file=?',(file,)).fetchone()==('pkg.Helper',)
        declarations={row[0] for row in conn.execute('SELECT fqcn FROM java_sources')}
        assert declarations>={'pkg.Unrelated','pkg.Kind','pkg.Marker'}
        assert not declarations & {'pkg.Empty','pkg.Commented','pkg.package-info'}
