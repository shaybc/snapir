package il.co.dcd.composermapper.storage;

import java.nio.file.*;
import java.util.*;

/** Persist production roots and declared visibility using captured Eclipse metadata. */
final class JavaSourceOwnership {
    private final AnalysisSession session;
    private final AnalysisStore store;
    JavaSourceOwnership(AnalysisSession session){this.session=session;store=session.store;}
    void build() {
        store.execute("CREATE TABLE java_projects(name TEXT PRIMARY KEY,path TEXT,declared INTEGER)");
        store.execute("CREATE TABLE java_roots(project TEXT,root TEXT,PRIMARY KEY(project,root))");
        store.execute("CREATE TABLE java_project_refs(project TEXT,target TEXT,PRIMARY KEY(project,target))");
        store.execute("CREATE TABLE java_sources(file TEXT PRIMARY KEY,fqcn TEXT,project TEXT,root TEXT)");
        store.execute("CREATE INDEX source_names ON java_sources(fqcn)");
        var owners=new TreeSet<Path>();
        for(var row:store.rows("SELECT path FROM files WHERE relative_path LIKE '%/.project' OR relative_path LIKE '%/.classpath' OR relative_path IN ('.project','.classpath') LIMIT 10000"))owners.add(Path.of(row[0]).getParent());
        for(Path project:owners) {
            String file=project.resolve(".project").toString();
            String name=store.scalar("SELECT n.value FROM xml_nodes n JOIN xml_nodes e ON n.parent=e.id WHERE e.file=? AND e.name='name' AND n.type=3 LIMIT 1",file);
            boolean declared=store.scalar("SELECT path FROM files WHERE path=?",file)!=null;
            if(name==null||name.isBlank())name=project.getFileName().toString();
            if(store.scalar("SELECT name FROM java_projects WHERE name=?",name)!=null){issue("Duplicate Eclipse project name: "+name);continue;}
            store.execute("INSERT INTO java_projects VALUES (?,?,?)",name,project.toString(),declared?1:0);
            for(var row:store.rows("SELECT n.value FROM xml_nodes n JOIN xml_nodes e ON e.id=n.parent JOIN xml_nodes p ON p.id=e.parent WHERE n.file=? AND e.name='project' AND p.name='projects' AND n.type=3",file))store.execute("INSERT OR IGNORE INTO java_project_refs VALUES (?,?)",name,row[0]);
            String classpath=project.resolve(".classpath").toString();
            if(store.scalar("SELECT path FROM files WHERE path=?",classpath)==null){conventional(project,name);continue;}
            for(var row:store.rows("SELECT n.id,a.value FROM xml_nodes n JOIN xml_attributes a ON a.node=n.id AND a.name='path' JOIN xml_attributes k ON k.node=n.id AND k.name='kind' WHERE n.file=? AND n.name='classpathentry' AND k.value='src'",classpath)) {
                String value=row[1];
                if(test(Path.of(value)))continue;
                if(store.scalar("SELECT a.node FROM xml_attributes a JOIN xml_attributes v ON a.node=v.node JOIN xml_nodes n ON n.id=a.node JOIN xml_nodes p ON p.id=n.parent WHERE p.parent=? AND a.name='name' AND a.value='test' AND v.name='value' AND v.value='true' LIMIT 1",row[0])!=null)continue;
                if(value.startsWith("/")){store.execute("UPDATE java_projects SET declared=1 WHERE name=?",name);store.execute("INSERT OR IGNORE INTO java_project_refs VALUES (?,?)",name,value.substring(1));}
                else root(name,project.resolve(value));
            }
        }
        try(var paths=Files.walk(session.root)) {
            var candidates=paths.filter(Files::isDirectory).filter(path->path.equals(session.root)||path.getFileName().toString().equals("src")).iterator();
            while(candidates.hasNext()) {
                Path candidate=candidates.next();Path project=candidate.equals(session.root)?candidate:candidate.getParent();
                if(owners.stream().anyMatch(project::startsWith))continue;
                String name=session.root.relativize(project).toString();if(name.isEmpty())name=".";
                store.execute("INSERT OR IGNORE INTO java_projects VALUES (?,?,0)",name,project.toString());conventional(project,name);
            }
        }catch(java.io.IOException error){throw new IllegalStateException(error);}
        if(owners.isEmpty()&&"0".equals(store.scalar("SELECT count(*) FROM java_roots")))root(".",session.root);
        for(var row:store.rows("SELECT project,root FROM java_roots ORDER BY project,root LIMIT 10000")) {
            Path root=Path.of(row[1]);String prefix=root.toString()+java.io.File.separator;
            // java_classes has no ordinal: traverse the indexed file key instead.
            String after="";
            while(true) {
                var page=store.rows("SELECT file,fqcn,package FROM java_classes WHERE file>? AND substr(file,1,?)=? ORDER BY file LIMIT 250",after,prefix.length(),prefix);
                if(page.isEmpty())break;
                for(var value:page) {
                    Path path=Path.of(value[0]);after=value[0];Path relative=root.relativize(path);
                    if(test(relative))continue;
                    String expected=(value[2]==null||value[2].isEmpty()?"":value[2].replace('.',java.io.File.separatorChar)+java.io.File.separator)+path.getFileName();
                    if(!relative.toString().equals(expected)){issue("Package does not match source root: "+path);continue;}
                    String fqcn=(value[2]==null||value[2].isEmpty()?"":value[2]+".")+path.getFileName().toString().replaceFirst("\\.java$","");
                    store.execute("INSERT OR REPLACE INTO java_sources VALUES (?,?,?,?)",value[0],fqcn,row[0],row[1]);
                }
            }
        }
        for(var row:store.rows("SELECT project,target FROM java_project_refs WHERE target NOT IN (SELECT project FROM java_roots)"))issue("Unresolved project reference from "+row[0]+": "+row[1]);
    }
    private void conventional(Path project,String name){for(String suffix:List.of("src/main/java","src")){Path candidate=project.resolve(suffix);if(Files.isDirectory(candidate)){root(name,candidate);return;}}}
    private void root(String project,Path candidate){Path value=candidate.toAbsolutePath().normalize();if(!value.startsWith(session.root))issue("Source root outside workspace: "+value);else if(!Files.isDirectory(value))issue("Missing source root: "+value);else store.execute("INSERT OR IGNORE INTO java_roots VALUES (?,?)",project,value.toString());}
    private static boolean test(Path path){for(Path part:path)if(Set.of("test","tests","test-fixtures").contains(part.toString().toLowerCase(Locale.ROOT)))return true;return false;}
    private void issue(String message){store.execute("INSERT INTO records(collection,data) VALUES ('source_issues',?)",StoredJson.encode(Map.of("message",message)));}
}
