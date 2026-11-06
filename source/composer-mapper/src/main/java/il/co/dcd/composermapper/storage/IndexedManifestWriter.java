package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import il.co.dcd.composermapper.render.VaultManifestWriter;
import il.co.dcd.composermapper.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Publish bounded index metadata; note inventory/consuming contexts stay in SQLite. */
public final class IndexedManifestWriter extends VaultManifestWriter {
    private final AnalysisSession session;
    private final AnalysisStore store;
    private final String workspace;
    private int publishedCount=-1;
    public IndexedManifestWriter(AnalysisSession session,String workspace){super(workspace);this.session=session;store=session.store;this.workspace=workspace;}
    @Override public void useCanonicalLayout(){}
    @Override public void reserve(SourceDefinitionIdentity source,String channel,String operation,String path){
        String owner=source.kind()+" "+source.file()+"#"+source.selector()+" "+channel+"/"+operation;
        String previous=store.scalar("SELECT owner FROM reservations WHERE path=?",path.toLowerCase(Locale.ROOT));
        if(previous!=null)throw new IllegalArgumentException("Duplicate note path before writing: "+path+" | first: "+previous+" | conflicting: "+owner);
        store.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?)",path.toLowerCase(Locale.ROOT),owner,source.key(workspace),channel,operation,SourceDefinitionIdentity.digest(channel,source.key(workspace)));
    }
    @Override public Map<String,Object> record(Path vault,SourceDefinitionIdentity source,String channel,String operation,String operationIdentity,String path,Map<String,Object> extra){
        String definition=source.key(workspace),usage=SourceDefinitionIdentity.digest(channel,operationIdentity,definition,path);
        Map<String,Object> entry=new LinkedHashMap<>();
        entry.put("kind",source.kind());entry.put("entity_id",source.name());entry.put("definition_id",definition);entry.put("usage_id",usage);
        entry.put("channel",channel);entry.put("operation_id",operation);entry.put("operation_identity",operationIdentity);entry.put("note",path);
        entry.put("definition_channel",source.channel());entry.put("source_relative_path",source.relativePath());entry.put("source_selector",source.selector());entry.put("source_hash",source.revision());
        entry.putAll(extra);
        // Per-context bindings are separately indexed; the record remains bounded to one operation.
        if(store.scalar("SELECT data FROM notes WHERE path=?",path)!=null)throw new IllegalArgumentException("Duplicate note identity: "+path);
        store.execute("UPDATE notes SET definition=?,kind=?,entity_id=?,source_relative_path=?,source_selector=?,source_hash=?,channel=?,operation_id=?,operation_identity=?,usage_id=?,data=? WHERE path=?",
            definition,source.kind(),source.name(),source.relativePath(),source.selector(),source.revision(),channel,operation,operationIdentity,usage,StoredJson.encode(entry),path);
        return entry;
    }
    @Override public void operationContexts(List<Map<String,Object>> contexts){
        // Contexts are already disk-backed. Normalize lookup bindings for joins/counts.
        store.execute("CREATE TABLE operation_context_index(ordinal INTEGER PRIMARY KEY,identity TEXT UNIQUE,channel TEXT,name TEXT,definition TEXT,note TEXT,data TEXT)");
        store.execute("CREATE INDEX context_names ON operation_context_index(channel,name)");
        store.execute("CREATE TABLE context_parts(context TEXT,kind TEXT,key TEXT,data TEXT,PRIMARY KEY(context,kind,key))");
        store.execute("CREATE TABLE context_calls(context TEXT,ordinal INTEGER,target TEXT,detail TEXT,PRIMARY KEY(context,ordinal))");
        store.execute("CREATE TABLE context_java_roots(context TEXT,file TEXT,PRIMARY KEY(context,file))");
        var roots=new CanonicalComponentRoots(session);
        for(var context:contexts) {
            String id=context.get("operation_identity").toString();
            roots.contextRoots(id,context.get("definition_id").toString(),context.get("channel").toString());
            ((Map<String,String>)context.get("references")).forEach((key,note)->store.execute("INSERT OR REPLACE INTO context_bindings VALUES (?,?,?,?)",id,"reference",key,note));
            var metadata=new LinkedHashMap<>(context);
            for(String kind:List.of("references","transition_targets")) {
                var parts=(Map<String,Object>)metadata.remove(kind);
                if(parts!=null)parts.forEach((key,value)->store.execute("INSERT INTO context_parts VALUES (?,?,?,?)",id,kind,key,StoredJson.encode(Map.of("value",value))));
            }
            for(String kind:List.of("step_notes","calls","java_resolution")) {
                var parts=(List<Object>)metadata.remove(kind);if(parts==null)continue;
                for(int i=0;i<parts.size();i++) {
                    Object part=parts.get(i);store.execute("INSERT INTO context_parts VALUES (?,?,?,?)",id,kind,Integer.toString(i),StoredJson.encode(Map.of("value",part)));
                    if(kind.equals("step_notes"))store.execute("INSERT OR REPLACE INTO context_bindings VALUES (?,?,?,?)",id,"step",Integer.toString(i),part);
                    if(kind.equals("calls")){var call=(Map<String,Object>)part;store.execute("INSERT INTO context_calls VALUES (?,?,?,?)",id,i,call.get("target_context"),call.get("detail"));}
                }
            }
            store.execute("INSERT INTO operation_context_index(identity,channel,name,definition,note,data) VALUES (?,?,?,?,?,?)",id,context.get("channel"),context.get("operation_id"),context.get("definition_id"),context.get("note"),StoredJson.encode(metadata));
        }
    }
    @Override public int noteCount(){return publishedCount>=0?publishedCount:Integer.parseInt(store.scalar("SELECT count(*) FROM notes WHERE definition IS NOT NULL"));}
    @Override public void finish(Path vault,List<Map<String,Object>> diagnostics,List<String> channels,Consumer<String> progress)throws IOException {
        session.verifySources();
        store.execute("CREATE TABLE IF NOT EXISTS note_consumers(definition TEXT,context TEXT,PRIMARY KEY(definition,context))");
        store.execute("INSERT OR IGNORE INTO note_consumers SELECT n.definition,b.context FROM context_bindings b JOIN notes n ON n.path=b.note");
        String after="";int rendered=0;
        while(true) {
            var page=store.rows("SELECT path,kind,definition,usage_id,operation_identity,channel FROM notes WHERE path>? ORDER BY path LIMIT 100",after);
            if(page.isEmpty())break;
            for(var note:page) {
                String content=store.scalar("SELECT body FROM notes WHERE path=?",note[0]);
                if(note[2]!=null) {
                    int marker=content.indexOf("---\n");if(marker<0)throw new IOException("Missing note frontmatter: "+note[0]);
                    var entry=StoredJson.map(store.scalar("SELECT data FROM notes WHERE path=?",note[0]));
                    String metadata="vault_schema_version: 4\nqualified_entity_id: "+note[2]+"\nusage_id: "+note[3]+"\noperation_identity: "+note[4]
                        +"\nsource_workspace_id: "+workspace+"\nsource_relative_path: "+JsonOutput.encode(entry.get("source_relative_path"))
                        +"\nsource_selector: "+JsonOutput.encode(entry.get("source_selector"))+"\n";
                    if(!note[1].equals("operation"))metadata+="channel: "+JsonOutput.encode(note[5])+"\n";
                    content=content.substring(0,marker+4)+metadata+content.substring(marker+4);
                    if(note[1].equals("format")||note[1].equals("context")) {
                        boolean shared=Integer.parseInt(store.scalar("SELECT count(*) FROM note_consumers WHERE definition=?",note[2]))>1;
                        if(content.contains("\nshared: "))content=content.replaceFirst("\nshared: (true|false)","\nshared: "+shared);
                        else content=content.replaceFirst("\nconversion_status:","\nshared: "+shared+"\nconversion_status:");
                    }
                }
                Path target=vault.resolve(note[0]);Files.createDirectories(target.getParent());
                String hash;
                try {
                    byte[] bytes=content.getBytes(StandardCharsets.UTF_8);
                    hash=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
                    if(!session.reuseNote(note[0],target,hash))Files.write(target,bytes);
                }catch(java.security.NoSuchAlgorithmException error){throw new IOException(error);}
                store.execute("UPDATE notes SET note_hash=?,body=NULL WHERE path=?",hash,note[0]);
                after=note[0];
                if(++rendered%100==0)progress.accept("Rendered indexed note "+rendered+"/"+noteCount());
            }
        }
        progress.accept("Reused "+session.reusedNotes()+" unchanged finalized notes.");
        for(String channel:channels)store.execute("INSERT INTO sets VALUES ('channels',?)",channel);
        // Indexed generation writes diagnostics directly to this relation.
        store.execute("INSERT OR REPLACE INTO revision VALUES ('complete','true')");
        store.execute("INSERT OR REPLACE INTO revision VALUES ('workspace',?)",workspace);
        store.execute("INSERT OR REPLACE INTO revision VALUES ('source_root',?)",session.root.toString());
        store.checkpoint();
        String parserPolicy=store.scalar("SELECT value FROM revision WHERE key='analysis_policy'");
        String resolverPolicy=store.scalar("SELECT value FROM revision WHERE key='resolution_policy'");
        publishedCount=noteCount();
        store.close();
        Map<String,Object> descriptor=new LinkedHashMap<>();
        descriptor.put("vault_schema_version",4);descriptor.put("identity_version",1);descriptor.put("producer","composer-mapper");
        descriptor.put("workspace_id",workspace);descriptor.put("complete",true);descriptor.put("analysis_store","analysis/analysis.sqlite");
        descriptor.put("analysis_hash",FileUtil.rawSha256(session.database));descriptor.put("entity_count",noteCount());
        descriptor.put("reused_note_count",session.reusedNotes());
        descriptor.put("producer_jdk",System.getProperty("java.runtime.version"));descriptor.put("source_language_level",Runtime.version().feature());
        descriptor.put("parser_policy",parserPolicy);descriptor.put("resolver_policy",resolverPolicy);descriptor.put("budgets",session.settings.metadata());
        descriptor.put("capabilities",List.of("indexed-xml","ast-java","java-edges-v1","original-consumers-v1","context-java-roots-v1","paged-inventory"));
        Path temporary=vault.resolve("vault-manifest.json.tmp");
        Files.writeString(temporary,JsonOutput.encode(descriptor)+"\n",StandardCharsets.UTF_8);
        Files.move(temporary,vault.resolve("vault-manifest.json"),StandardCopyOption.ATOMIC_MOVE);
    }
}
