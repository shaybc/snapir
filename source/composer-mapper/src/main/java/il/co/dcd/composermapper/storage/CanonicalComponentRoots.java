package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.util.XmlUtil;
import java.nio.file.*;
import java.util.*;
import org.w3c.dom.*;

/** Compact original-operation consumers; Java reference sites are never expanded per operation. */
final class CanonicalComponentRoots {
    private final AnalysisSession session;private final AnalysisStore store;
    private boolean contextMode;
    private record Definition(String node,String kind,String name,String file,String channel,String selector) {}
    CanonicalComponentRoots(AnalysisSession session){this.session=session;store=session.store;}
    void build() {
        store.execute("CREATE TABLE canonical_definitions(ordinal INTEGER PRIMARY KEY,node TEXT UNIQUE,kind TEXT,name TEXT,file TEXT,channel TEXT,selector TEXT)");
        store.execute("CREATE INDEX canonical_names ON canonical_definitions(kind,name,channel,file)");
        store.execute("CREATE TABLE channel_mappings(channel TEXT,tag TEXT,fqcn TEXT,source TEXT,origin_channel TEXT,group_name TEXT,PRIMARY KEY(channel,tag))");
        store.execute("CREATE TABLE channel_imports(channel TEXT,target TEXT,PRIMARY KEY(channel,target))");
        store.execute("CREATE TABLE configured_counts(operation TEXT,node TEXT,kind TEXT,implementation TEXT,valid INTEGER,weight INTEGER,PRIMARY KEY(operation,node,kind,implementation,valid))");
        store.execute("CREATE INDEX configured_targets ON configured_counts(implementation,operation)");
        store.execute("CREATE TABLE operation_roots(operation TEXT,implementation TEXT,weight INTEGER,direct_weight INTEGER,PRIMARY KEY(operation,implementation))");
        store.execute("CREATE TEMP TABLE operation_uses(node TEXT,caller TEXT,kind TEXT,implementation TEXT,valid INTEGER,PRIMARY KEY(node,caller))");
        store.execute("INSERT INTO canonical_definitions(node,kind,name,file,channel,selector) SELECT n.id,CASE n.name WHEN 'CCDSEServerOperation' THEN 'operation' WHEN 'fmtDef' THEN 'format' WHEN 'context' THEN 'context' ELSE 'opStep' END,a.value,n.file,upper(f.channel),n.selector FROM xml_nodes n JOIN files f ON f.path=n.file JOIN xml_attributes a ON a.node=n.id AND a.name='id' WHERE n.name IN ('CCDSEServerOperation','fmtDef','context','opStep') AND lower(f.relative_path) NOT LIKE '%/pom.xml' ORDER BY n.file,n.selector");
        for(var row:store.rows("SELECT DISTINCT upper(channel) FROM files WHERE lower(relative_path) LIKE '%/dse.ini' ORDER BY 1 LIMIT 10000"))try{mappings(row[0],new HashSet<>());}catch(IllegalArgumentException error){issue(error.getMessage());}
        int completed=0;
        for(var operation:definitions("kind='operation'")) {
            store.execute("DELETE FROM operation_uses");
            visit(operation,operation,"operation",new HashSet<>());
            store.execute("INSERT INTO configured_counts SELECT ?,node,kind,implementation,valid,count(*) FROM operation_uses GROUP BY node,kind,implementation,valid",operation.node());
            if(++completed%100==0)System.out.println("Counted original operation consumers: "+completed+" operations.");
        }
        store.execute("INSERT INTO operation_roots SELECT operation,implementation,sum(CASE WHEN valid=1 THEN weight ELSE 0 END),sum(weight) FROM configured_counts WHERE implementation<>'' GROUP BY operation,implementation");store.commit();
    }
    private Iterable<Definition> definitions(String clause,Object... args){return store.sequence("canonical_definitions",clause,args,"node,kind,name,file,channel,selector",row->new Definition(row[0],row[1],row[2],row[3],row[4],row[5]));}
    /** Resolve consuming-channel roots separately from original global consumer counts. */
    void contextRoots(String context,String definition,String channel) {
        String node=store.scalar("SELECT d.node FROM canonical_definitions d JOIN files f ON f.path=d.file JOIN notes n ON n.source_relative_path=f.relative_path AND n.source_selector=d.selector WHERE n.definition=? AND d.kind='operation'",definition);
        if(node==null)throw new IllegalArgumentException("Missing canonical operation for execution context: "+context);
        Definition source=definitions("node=?",node).iterator().next();
        Definition operation=new Definition(source.node(),source.kind(),source.name(),source.file(),channel,source.selector());
        store.execute("DELETE FROM operation_uses");
        contextMode=true;
        try{visit(operation,source,"operation",new HashSet<>());}finally{contextMode=false;}
        store.execute("INSERT INTO context_java_roots SELECT ?,implementation FROM operation_uses WHERE implementation<>'' GROUP BY implementation",context);
    }
    private void mappings(String channel,Set<String> active) {
        if(store.set("canonical_channels").contains(channel))return;
        if(!active.add(channel))throw new IllegalArgumentException("Channel import cycle: "+channel);
        var files=store.rows("SELECT path FROM files WHERE upper(channel)=? AND lower(relative_path) LIKE '%/dse.ini' LIMIT 2",channel);
        if(files.size()!=1)throw new IllegalArgumentException("Missing or ambiguous channel configuration: "+channel);
        Element root=session.document(Path.of(files.getFirst()[0])).getDocumentElement();
        store.execute("INSERT OR IGNORE INTO channel_imports VALUES (?,?)",channel,channel);
        for(var collection:XmlUtil.childElements(root))if("import".equals(collection.getAttribute("id")))for(var entry:XmlUtil.childElements(collection)) {
            String imported=entry.getAttribute("id").toUpperCase(Locale.ROOT);if(imported.isEmpty())continue;
            mappings(imported,new HashSet<>(active));
            for(var prior:store.rows("SELECT m.tag FROM channel_mappings m JOIN channel_mappings p ON p.tag=m.tag AND p.channel=? WHERE m.channel=? AND m.fqcn<>p.fqcn LIMIT 1",channel,imported))throw new IllegalArgumentException("Conflicting inherited mapping for "+channel+"/"+prior[0]);
            store.execute("INSERT OR REPLACE INTO channel_mappings SELECT ?,tag,fqcn,source,origin_channel,group_name FROM channel_mappings WHERE channel=?",channel,imported);
            store.execute("INSERT OR IGNORE INTO channel_imports SELECT ?,target FROM channel_imports WHERE channel=?",channel,imported);
        }
        var locals=new HashMap<String,String>();
        for(var settings:XmlUtil.childElements(root))if(settings.getAttribute("id").equals("settings"))for(var tags:XmlUtil.childElements(settings))if(tags.getAttribute("id").equals("tags"))for(var group:XmlUtil.childElements(tags))for(var field:XmlUtil.childElements(group)) {
            String name=field.getAttribute("id"),fqcn=field.getAttribute("value");if(!field.getTagName().equals("field")||name.isEmpty()||fqcn.isEmpty())continue;
            if(locals.putIfAbsent(name,fqcn)!=null&&!locals.get(name).equals(fqcn))throw new IllegalArgumentException("Conflicting local mapping for "+channel+"/"+name);
            store.execute("INSERT OR REPLACE INTO channel_mappings VALUES (?,?,?,?,?,?)",channel,name,fqcn,session.root.relativize(Path.of(files.getFirst()[0])).toString().replace('\\','/'),channel,group.getAttribute("id"));
        }
        store.set("canonical_channels").add(channel);
    }
    private void visit(Definition operation,Definition definition,String caller,Set<String> active) {
        if(!active.add(definition.node())){issue(operation.name()+": recursive configured reference at "+definition.file()+definition.selector());return;}
        Element root=(Element)SqlXmlViews.node(store,definition.node());
        if(Set.of("format","context").contains(definition.kind()))bind(operation,definition,root,caller,definition.kind(),false);
        walk(operation,definition,root,root,caller,active);
    }
    private void walk(Definition operation,Definition definition,Element root,Element node,String caller,Set<String> active) {
        String tag=node.getTagName(),id=SqlXmlViews.identity(node);
        if(contextMode&&tag.equals("opStep")&&!il.co.dcd.composermapper.util.ChannelStepSelection.applies(node.getAttribute("onlyFor"),operation.channel()))return;
        List<String[]> refs=new ArrayList<>();
        if(tag.equals("refFormat")&&value(node.getAttribute("refid"))!=null)refs.add(new String[]{"format",value(node.getAttribute("refid"))});
        if(value(node.getAttribute("refFmt"))!=null)refs.add(new String[]{"format",value(node.getAttribute("refFmt"))});
        if(node==root&&definition.kind().equals("operation")&&value(node.getAttribute("operationContext"))!=null)refs.add(new String[]{"context",value(node.getAttribute("operationContext"))});
        if(node==root&&definition.kind().equals("context")&&value(node.getAttribute("parent"))!=null)refs.add(new String[]{"context",value(node.getAttribute("parent"))});
        for(var ref:refs) {
            var target=resolve(ref[0],ref[1],definition,operation);
            if(target==null){issue(operation.name()+": "+session.root.relativize(Path.of(definition.file()))+store.scalar("SELECT selector FROM xml_nodes WHERE id=?",id)+": Missing or ambiguous "+ref[0]+" reference: "+ref[1]);bind(operation,definition,node,caller,ref[0],true);}
            else visit(operation,target,caller+" -> "+definition.file()+store.scalar("SELECT selector FROM xml_nodes WHERE id=?",id),new HashSet<>(active));
        }
        if(!(node==root&&Set.of("format","context").contains(definition.kind()))&&!Set.of("refFormat","iniValue","field").contains(tag)) {
            boolean mapped=store.scalar("SELECT tag FROM "+mappingTable()+" WHERE channel=? AND tag=?",contextMode?operation.channel():definition.channel(),tag)!=null;
            if(tag.equals("opStep")||value(node.getAttribute("implClass"))!=null||value(node.getAttribute("javaClass"))!=null||mapped)
                bind(operation,definition,node,caller,node==root&&definition.kind().equals("operation")?"operation":null,false);
            else if(definition.kind().equals("format"))bind(operation,definition,node,caller,null,false);
        }
        for(var child:XmlUtil.childElements(node))walk(operation,definition,root,child,caller,active);
    }
    private Definition resolve(String kind,String name,Definition owner,Definition operation) {
        if(contextMode) {
            var candidates=store.rows("SELECT c.node,CASE WHEN d.owner<>'' THEN 1 ELSE 0 END,COALESCE(i.position,-1) FROM definitions d JOIN canonical_definitions c ON c.file=d.file AND c.selector=d.selector AND c.kind=d.kind LEFT JOIN context_imports i ON i.channel=? AND i.target=upper(d.channel) WHERE d.kind=? AND d.name=? AND (d.channel IS NULL OR i.target IS NOT NULL) AND (d.owner='' OR d.file=? AND d.owner=?) ORDER BY 2 DESC,3 DESC LIMIT 2",operation.channel(),kind,name,operation.file(),operation.selector());
            if(candidates.isEmpty()||candidates.size()>1&&candidates.get(0)[1].equals(candidates.get(1)[1])&&candidates.get(0)[2].equals(candidates.get(1)[2]))return null;
            return definitions("node=?",candidates.getFirst()[0]).iterator().next();
        }
        String clause="kind=? AND name=?";List<Object> args=new ArrayList<>(List.of(kind,name));
        if(store.scalar("SELECT node FROM canonical_definitions WHERE "+clause+" AND file=? LIMIT 1",kind,name,owner.file())!=null){clause+=" AND file=?";args.add(owner.file());}
        else if(owner.channel()!=null) {
            if(store.scalar("SELECT node FROM canonical_definitions WHERE "+clause+" AND channel=? LIMIT 1",kind,name,owner.channel())!=null)clause+=" AND channel=?";
            else clause+=" AND (channel IS NULL OR channel IN (SELECT target FROM "+(contextMode?"context_imports":"channel_imports")+" WHERE channel=?))";
            args.add(owner.channel());
        }
        if(!"1".equals(store.scalar("SELECT count(*) FROM canonical_definitions WHERE "+clause,args.toArray())))return null;
        return definitions(clause,args.toArray()).iterator().next();
    }
    private void bind(Definition operation,Definition definition,Element node,String caller,String kind,boolean error) {
        String tag=node.getTagName(),mappingTag=tag,channel=operation.channel()==null?definition.channel():operation.channel();
        if(tag.equals("opStep")&&value(node.getAttribute("implClass"))==null&&store.scalar("SELECT tag FROM "+mappingTable()+" WHERE channel=? AND tag=?",channel,node.getAttribute("id"))!=null)mappingTag=node.getAttribute("id");
        var mapping=store.rows("SELECT fqcn,source,group_name FROM "+mappingTable()+" WHERE channel=? AND tag=?",channel,mappingTag);
        String explicit=value(node.getAttribute("implClass"));if(explicit==null)explicit=value(node.getAttribute("javaClass"));
        String fqcn=explicit!=null?explicit:mapping.isEmpty()?null:mapping.getFirst()[0];
        if(kind==null)kind=tag.equals("opStep")||!mapping.isEmpty()&&mapping.getFirst()[2].equals("opSteps")?"opStep":!mapping.isEmpty()&&mapping.getFirst()[0].toLowerCase(Locale.ROOT).contains(".decorator.")?"decorator":"formatter";
        String implementation="";
        if(!kind.equals("format")&&(!kind.equals("context")||fqcn!=null)) {
            Path origin=explicit!=null||mapping.isEmpty()?Path.of(definition.file()):session.root.resolve(mapping.getFirst()[1]);
            String project=store.scalar("SELECT project FROM java_roots WHERE substr(?,1,length(root)+1)=root||? ORDER BY length(root) DESC LIMIT 1",origin.toString(),java.io.File.separator);
            String clause="fqcn=?";Object[] args={fqcn};
            if(store.scalar("SELECT file FROM java_sources WHERE fqcn=? AND project=? LIMIT 1",fqcn,project)!=null){clause+=" AND project=?";args=new Object[]{fqcn,project};}
            String count=store.scalar("SELECT count(*) FROM java_sources WHERE "+clause,args);
            if("1".equals(count))implementation=store.scalar("SELECT file FROM java_sources WHERE "+clause,args);
            else {
                error=true;
                String message=fqcn==null?"Java implementation mapping is unavailable":("0".equals(count)?"Java source is missing: ":"Java source is ambiguous: ")+fqcn;
                issue(operation.name()+": "+session.root.relativize(Path.of(definition.file())).toString().replace('\\','/')+store.scalar("SELECT selector FROM xml_nodes WHERE id=?",SqlXmlViews.identity(node))+": "+message);
            }
        }
        store.execute("INSERT OR REPLACE INTO operation_uses VALUES (?,?,?,?,?)",SqlXmlViews.identity(node),caller,kind,implementation,error?0:1);
    }
    private static String value(String text){if(text==null||text.isBlank()||text.strip().equalsIgnoreCase("nil"))return null;return text;}
    private String mappingTable(){return contextMode?"context_mappings":"channel_mappings";}
    private void issue(String message){store.execute("INSERT INTO records(collection,data) VALUES ('component_issues',?)",StoredJson.encode(Map.of("message",message)));}
}
