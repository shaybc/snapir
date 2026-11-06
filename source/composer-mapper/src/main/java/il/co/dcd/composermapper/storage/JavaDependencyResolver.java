package il.co.dcd.composermapper.storage;

import il.co.dcd.javaanalysis.*;
import java.util.*;

/** Resolve captured syntax through indexed declarations; never construct the project graph in RAM. */
final class JavaDependencyResolver {
    private final AnalysisStore store;
    JavaDependencyResolver(AnalysisStore store){this.store=store;}
    void build() {
        build(null);
    }
    void build(FileFactReuse reuse) {
        store.execute("CREATE TABLE java_edges(caller TEXT,target TEXT,offset INTEGER,kind TEXT,name TEXT,PRIMARY KEY(caller,target,offset))");
        store.execute("CREATE TABLE java_resolution_ready(file TEXT PRIMARY KEY)");
        store.execute("CREATE INDEX java_incoming ON java_edges(target,caller)");
        IndexedTypeLookup lookup;
        try{lookup=new IndexedTypeLookup(store.connection);}catch(java.sql.SQLException error){throw new IllegalStateException(error);}
        String revision=resolutionRevision();
        store.execute("INSERT OR REPLACE INTO revision VALUES ('resolution_policy',?)",revision);
        String after="";int completed=0;
        while(true) {
            var page=store.rows("SELECT s.file,c.package FROM java_sources s JOIN java_classes c ON c.file=s.file WHERE s.file>? ORDER BY s.file LIMIT 100",after);
            if(page.isEmpty())break;
            for(var source:page) {
                after=source[0];List<SourceReferenceResolver.Imported> imports=new ArrayList<>();
                if(reuse!=null&&reuse.edges(source[0],revision)) {
                    store.execute("INSERT INTO java_resolution_ready VALUES (?)",source[0]);
                    if(++completed%100==0)System.out.println("Reused/resolved Java dependencies: "+completed+" source files.");
                    continue;
                }
                Map<String,Set<String>> symbols=new HashMap<>();for(String kind:List.of("variable","type_parameter","local_type","method"))symbols.put(kind,new HashSet<>());
                for(var fact:store.sequence("java_facts","file=? AND kind<>'reference' AND kind NOT LIKE 'metadata:%'",new Object[]{source[0]},"kind,name,value",row->row)) {
                    if(fact[0].equals("import"))imports.add(new SourceReferenceResolver.Imported(fact[1],fact[2].equals("true")));
                    else if(symbols.containsKey(fact[0]))symbols.get(fact[0]).add(fact[1]);
                }
                var scope=new SourceReferenceResolver.Scope(source[0],Objects.requireNonNullElse(source[1],""),imports,symbols.get("variable"),symbols.get("type_parameter"),symbols.get("local_type"),symbols.get("method"));
                for(var fact:store.sequence("java_facts","file=? AND kind='reference'",new Object[]{source[0]},"name,value,extra",row->row)) {
                    var result=SourceReferenceResolver.resolve(fact[0],fact[1],scope,lookup);
                    if(result.issue()!=null)store.execute("INSERT INTO records(collection,data) VALUES ('dependency_issues',?)",StoredJson.encode(Map.of("file",source[0],"message",result.issue())));
                    for(String target:result.targets())if(!source[0].equals(target))store.execute("INSERT OR IGNORE INTO java_edges VALUES (?,?,?,?,?)",source[0],target,Long.parseLong(fact[2]),fact[1],fact[0]);
                }
                if(++completed%100==0)System.out.println("Resolved Java dependencies: "+completed+" source files.");
                store.execute("INSERT INTO java_resolution_ready VALUES (?)",source[0]);
            }
        }
        lookup.close();store.commit();
    }
    private String resolutionRevision() {
        try {
            var digest=java.security.MessageDigest.getInstance("SHA-256");
            for(Class<?> policy:List.of(JavaDependencyResolver.class,SourceReferenceResolver.class,IndexedTypeLookup.class))try(var input=policy.getResourceAsStream(policy.getSimpleName()+".class")){digest.update(input.readAllBytes());}
            for(String sql:List.of("SELECT file,fqcn,project,root FROM java_sources ORDER BY file","SELECT name,path,declared FROM java_projects ORDER BY name","SELECT project,target FROM java_project_refs ORDER BY project,target"))
                try(var statement=store.connection.createStatement();var rows=statement.executeQuery(sql)) {
                    int columns=rows.getMetaData().getColumnCount();
                    while(rows.next())for(int i=1;i<=columns;i++){String value=Objects.requireNonNullElse(rows.getString(i),"");byte[] bytes=value.getBytes(java.nio.charset.StandardCharsets.UTF_8);digest.update(java.nio.ByteBuffer.allocate(4).putInt(bytes.length).array());digest.update(bytes);}
                }
            return java.util.HexFormat.of().formatHex(digest.digest());
        }catch(Exception error){throw new IllegalStateException("Cannot fingerprint Java resolution policy",error);}
    }
}
