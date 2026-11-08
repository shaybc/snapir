package il.co.dcd.composermapper.storage;

import il.co.dcd.javaanalysis.*;
import il.co.dcd.composermapper.model.*;
import il.co.dcd.composermapper.util.FileUtil;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import org.w3c.dom.Document;

/** One indexed map build; explicit lifetime prevents shared mutable parser caches across runs. */
public final class AnalysisSession implements AutoCloseable {
    private static final ThreadLocal<AnalysisSession> ACTIVE=new ThreadLocal<>();
    public final AnalysisStore store;
    public final Path root,vault,database;
    private final Path realRoot;
    public final String workspace;
    public final AnalysisSettings settings;
    private boolean closed;
    private NoteReuse noteReuse;
    private boolean restoredIndex;
    private boolean rejectedCheckpoint;
    private String checkpointScope = "";
    private final Map<Path,JavaClassDef> javaMetadata=new LinkedHashMap<>(64,0.75f,true);
    private final Map<Path,Long> metadataWeights=new HashMap<>();private long metadataBytes;
    private static final Set<String> DESCRIPTORS=Set.of("ejb-jar.xml","web.xml","application.xml","application-client.xml","ra.xml","persistence.xml","beans.xml","faces-config.xml","validation.xml");

    public AnalysisSession(Path root,Path vault,String workspace) throws Exception {
        this(root,vault,workspace,AnalysisSettings.defaults());
    }
    public AnalysisSession(Path root,Path vault,String workspace,AnalysisSettings settings) throws Exception {
        this(root,vault,workspace,settings,null,"");
    }
    /** Restores only a completed, compatible source index into a fresh output directory. */
    public AnalysisSession(Path root,Path vault,String workspace,AnalysisSettings settings,Path recovery,String scope) throws Exception {
        this.settings=settings;
        this.root=root;this.vault=vault;this.workspace=workspace;
        realRoot=root.toRealPath();
        if(workspace==null||workspace.isBlank())throw new IllegalArgumentException("Indexed maps require a stable workspace ID");
        if(vault.startsWith(root)||root.startsWith(vault))throw new IllegalArgumentException("Map destination must be separate from source");
        if(Files.exists(vault))try(var entries=Files.list(vault)){if(entries.findAny().isPresent())throw new IllegalArgumentException("Indexed map requires a fresh destination");}
        Files.createDirectories(vault);
        Files.writeString(vault.resolve("vault-generation.json"),"{\"vault_schema_version\":4,\"complete\":false}\n",StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
        database=vault.resolve("analysis/analysis.sqlite");
        checkpointScope=scope;
        restoredIndex=IndexCheckpoint.restore(recovery,database,root,workspace,settings,scope);
        rejectedCheckpoint=IndexCheckpoint.exists(recovery)&&!restoredIndex;
        store=new AnalysisStore(database,settings.sqliteCacheMib());
    }

    public static AnalysisSession current(){return ACTIVE.get();}

    /** Capture each original file once; reusable facts serve every later catalog/writer lookup. */
    public void prepare() throws Exception {
        prepare(null,false);
    }
    public void prepare(Path prior,boolean recovery) throws Exception {
        try (var progress = new il.co.dcd.composermapper.service.MapperProgress(vault.resolve("composer-mapper.log"),System.nanoTime())) {
            if (restoredIndex) {
                progress.event("Resuming completed source index; restarting map rendering in fresh destination: " + vault, true);
                store.execute("CREATE TEMP TABLE operation_uses(node TEXT,caller TEXT,kind TEXT,implementation TEXT,valid INTEGER,PRIMARY KEY(node,caller))");
                ACTIVE.set(this);
                return;
            }
            prepareFacts(rejectedCheckpoint ? null : prior,recovery,progress);
        }
    }

    private void prepareFacts(Path prior,boolean recovery,il.co.dcd.composermapper.service.MapperProgress progress) throws Exception {
        String policy=FileFactReuse.policy();
        store.execute("INSERT OR REPLACE INTO revision VALUES ('analysis_policy',?)",policy);
        store.execute("INSERT OR REPLACE INTO revision VALUES ('source_root',?)",root.toString());store.commit();
        var reuse=new FileFactReuse(store,prior,recovery,policy);
        if(prior!=null&&!recovery)noteReuse=new NoteReuse(prior);
        List<SourceSnapshot> batch=new ArrayList<>();long weight=0;int files=0;
        int reused=0;
        try(var paths=Files.walk(root)) {
            var iterator=paths.filter(Files::isRegularFile).iterator();
            while(iterator.hasNext()) {
                Path file=iterator.next().toAbsolutePath().normalize();
                if(!file.toRealPath().startsWith(realRoot))throw new IllegalArgumentException("Source file escapes workspace: "+file);
                String name=file.getFileName().toString().toLowerCase(Locale.ROOT);
                if(!sourceFile(file))continue;
                boolean java=name.endsWith(".java");
                progress.event("Starting source capture: " + file, true);
                String channel=null;for(int i=0;i<file.getNameCount()-1;i++)if(file.getName(i).toString().equalsIgnoreCase("channel")){channel=file.getName(i+1).toString();break;}
                if(java) {
                    if(Files.size(file)>settings.javaFileBytes())throw new IllegalArgumentException("Java source exceeds configured analysis size limit: "+file);
                    long size=Files.size(file)*2;
                    if(!batch.isEmpty()&&(batch.size()>=settings.batchFiles()||weight+size>settings.batchBytes())){JavaFactReader.analyze(store,batch);batch.clear();weight=0;}
                    var source=SourceSnapshot.read(file,true);
                    store.execute("INSERT INTO files VALUES (?,?,?,?,?,?,0)",file.toString(),root.relativize(file).toString().replace('\\','/'),channel,"JAVA",source.hash(),source.encoding());
                    if(reuse.copy(file.toString(),source.hash(),"JAVA"))reused++;
                    else {batch.add(source);weight+=size;}
                } else {
                    Path captured=Files.createTempFile("mapper-xml-source-",".snapshot");
                    try {
                        var digest=MessageDigest.getInstance("SHA-256");
                        try(var input=new DigestInputStream(Files.newInputStream(file),digest);var output=Files.newOutputStream(captured)){input.transferTo(output);}
                        String hash=HexFormat.of().formatHex(digest.digest());
                        store.execute("INSERT INTO files VALUES (?,?,?,?,?,?,0)",file.toString(),root.relativize(file).toString().replace('\\','/'),channel,"XML",hash,"xml-declaration");
                        try {if(reuse.copy(file.toString(),hash,"XML"))reused++;else {XmlFactReader.read(store,file,captured);store.execute("UPDATE files SET complete=1 WHERE path=?",file.toString());}}
                        catch(Exception error){throw new IOException("XML parse error: "+file+": "+error.getMessage(),error);}
                    } finally {Files.deleteIfExists(captured);}
                }
                if(++files%100==0)System.out.println("Analysis snapshot: "+files+" files captured.");
            }
        }
        if(!batch.isEmpty())JavaFactReader.analyze(store,batch);
        System.out.println("Captured "+files+" source files; reused "+reused+" unchanged file analyses.");
        store.execute("INSERT OR REPLACE INTO revision VALUES ('file_count',?)",Integer.toString(files));
        store.execute("INSERT OR REPLACE INTO revision VALUES ('reused_file_count',?)",Integer.toString(reused));
        store.commit();
        if(store.scalar("SELECT path FROM files WHERE complete<>1 LIMIT 1")!=null||store.scalar("SELECT data FROM records WHERE collection='java_issues' AND json_extract(data,'$.file')='' LIMIT 1")!=null)throw new IllegalStateException("Java syntax analysis failed; indexed map cannot be published");
        new JavaSourceOwnership(this).build();
        new JavaDependencyResolver(store).build(reuse);
        reuse.finish();
        ACTIVE.set(this);
        new CanonicalComponentRoots(this).build();
    }

    /** Indicates that catalog construction can use the verified persisted index directly. */
    public boolean restoredIndex(){return restoredIndex;}

    /** Saves the completed index before any operation views or inventory output are rendered. */
    public void checkpointIndex() throws IOException {
        try { IndexCheckpoint.save(this,checkpointScope); }
        catch (Exception error) { throw new IOException("Could not save completed source index",error); }
    }

    static boolean sourceFile(Path file) {
        String name=file.getFileName().toString().toLowerCase(Locale.ROOT);
        return !DESCRIPTORS.contains(name)&&(name.endsWith(".java")||name.endsWith(".xml")||name.endsWith(".ini")||name.equals(".classpath")||name.equals(".project"));
    }

    public Document document(Path path){return SqlXmlViews.document(store,path.toAbsolutePath().normalize());}
    public boolean reuseNote(String relative,Path target,String digest)throws IOException{return noteReuse!=null&&noteReuse.copy(relative,target,digest);}
    public int reusedNotes(){return noteReuse==null?0:noteReuse.count();}
    /** Capture the mapper's actual effective registry, including its implicit XML base. */
    public void contextMappings(String channel,il.co.dcd.composermapper.index.Indexes index,List<String> chain) {
        if(!store.set("captured_context_mappings").add(channel))return;
        store.execute("CREATE TABLE IF NOT EXISTS context_mappings(channel TEXT,tag TEXT,fqcn TEXT,source TEXT,origin_channel TEXT,group_name TEXT,PRIMARY KEY(channel,tag))");
        store.execute("CREATE TABLE IF NOT EXISTS context_imports(channel TEXT,target TEXT,position INTEGER,PRIMARY KEY(channel,target))");
        for(int position=0;position<chain.size();position++)store.execute("INSERT OR IGNORE INTO context_imports VALUES (?,?,?)",channel,chain.get(position),position);
        for(var entry:index.tagToClass().entrySet()) {
            Path origin=index.tagToSource().get(entry.getKey());
            if(origin==null)throw new IllegalArgumentException("Effective tag mapping has no source: "+channel+"/"+entry.getKey());
            String group=store.scalar("SELECT g.value FROM xml_attributes a JOIN xml_nodes n ON n.id=a.node JOIN xml_attributes v ON v.node=n.id AND v.name='value' JOIN xml_attributes g ON g.node=n.parent AND g.name='id' WHERE n.file=? AND a.name='id' AND a.value=? AND v.value=? LIMIT 1",origin.toString(),entry.getKey(),entry.getValue());
            store.execute("INSERT INTO context_mappings VALUES (?,?,?,?,?,?)",channel,entry.getKey(),entry.getValue(),root.relativize(origin).toString().replace('\\','/'),store.scalar("SELECT upper(channel) FROM files WHERE path=?",origin.toString()),Objects.requireNonNullElse(group,""));
        }
    }
    /** Reject an oversized business-model fragment before existing parsers build its lists. */
    public void requireDefinitionBudget(org.w3c.dom.Element element) {
        String node=SqlXmlViews.identity(element);
        String bytes=store.scalar("WITH RECURSIVE children(id) AS (SELECT ? UNION ALL SELECT n.id FROM xml_nodes n JOIN children c ON n.parent=c.id) SELECT COALESCE(sum(128+4*length(COALESCE(n.name,''))+4*length(COALESCE(n.value,''))+(SELECT COALESCE(sum(4*length(a.name)+4*length(a.value)+64),0) FROM xml_attributes a WHERE a.node=n.id)),0) FROM xml_nodes n JOIN children c ON c.id=n.id",node);
        if(Long.parseLong(bytes)>4L*1024*1024)throw new IllegalArgumentException("XML definition exceeds the 4 MiB materialization budget: "+store.scalar("SELECT file||selector FROM xml_nodes WHERE id=?",node));
    }
    public String hash(Path path){return store.scalar("SELECT hash FROM files WHERE path=?",path.toAbsolutePath().normalize().toString());}
    public String javaClassName(Path path){return store.scalar("SELECT fqcn FROM java_classes WHERE file=?",path.toAbsolutePath().normalize().toString());}
    public JavaClassDef javaClass(Path path){
        Path absolute=path.toAbsolutePath().normalize();var cached=javaMetadata.get(absolute);if(cached!=null)return cached;
        long weight=512+Long.parseLong(store.scalar("SELECT COALESCE(sum(160+2*length(name)+2*length(value)),0) FROM java_facts WHERE file=? AND (kind='import' OR kind LIKE 'metadata:%')",absolute.toString()));
        if(weight>4L*1024*1024)throw new IllegalArgumentException("Java metadata exceeds the 4 MiB materialization budget: "+absolute);
        var value=StoredJavaMetadata.read(store,absolute);if(value==null)return null;
        if(weight<=2L*1024*1024) {
            while(!javaMetadata.isEmpty()&&(javaMetadata.size()>=64||metadataBytes+weight>8L*1024*1024)){var oldest=javaMetadata.entrySet().iterator();Path key=oldest.next().getKey();metadataBytes-=metadataWeights.remove(key);oldest.remove();}
            javaMetadata.put(absolute,value);metadataWeights.put(absolute,weight);metadataBytes+=weight;
        }
        return value;
    }
    public List<DiscoveredFile> discoveredFiles(String channel){return StoredFileDiscovery.discover(this,channel);}

    public void diagnostics(List<Map<String,Object>> diagnostics) {
        stageNote(vault.resolve("analysis/entity-collisions.md"),"# Scoped resolution diagnostics\n\nDiagnostic records are paged under [diagnostics](diagnostics/).\n");
        int page=0,count=0;StringBuilder text=new StringBuilder("# Scoped resolution diagnostics\n\n");
        for(var diagnostic:diagnostics) {
            String line="- "+diagnostic.get("operation")+": "+diagnostic.get("detail")+"\n";
            if(count>=250||text.length()+line.length()>2*1024*1024){stageNote(vault.resolve("analysis/diagnostics/"+(++page)+".md"),text.toString());text=new StringBuilder("# Scoped resolution diagnostics\n\n");count=0;}
            text.append(line);count++;
        }
        if(count>0)stageNote(vault.resolve("analysis/diagnostics/"+(++page)+".md"),text.toString());
    }

    public boolean stageNote(Path path,String content){
        Path absolute=path.toAbsolutePath().normalize();
        if(!absolute.startsWith(vault)||!path.toString().endsWith(".md"))return false;
        if(content.length()*2L>4L*1024*1024)throw new IllegalArgumentException("Markdown note exceeds the 4 MiB rendering budget: "+path);
        String relative=vault.relativize(absolute).toString().replace('\\','/');
        store.execute("INSERT INTO notes(path,body) VALUES (?,?) ON CONFLICT(path) DO UPDATE SET body=excluded.body",relative,content);
        return true;
    }

    /** Pin source bytes at publication; hashing is not another syntax parse. */
    public void verifySources(){
        IndexCheckpoint.verifySources(store.connection,root);
    }

    public void close(){if(closed)return;closed=true;ACTIVE.remove();try{if(noteReuse!=null)noteReuse.close();}finally{store.close();}}
}
