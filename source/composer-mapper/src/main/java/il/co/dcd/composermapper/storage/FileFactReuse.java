package il.co.dcd.composermapper.storage;

import java.nio.file.*;
import java.security.*;
import java.util.*;
import il.co.dcd.composermapper.util.FileUtil;

/** Reuse only complete file facts from the same analyzer/JDK policy and source byte revision. */
final class FileFactReuse {
    private final AnalysisStore store;
    private boolean attached;
    static String policy()throws Exception {
        var hash=MessageDigest.getInstance("SHA-256");hash.update(("indexed-v1-policy-1|"+System.getProperty("java.runtime.version")).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        for(String resource:List.of("il/co/dcd/javaanalysis/SourceAnalysis.class","il/co/dcd/javaanalysis/ReferenceCollector.class",
            "il/co/dcd/javaanalysis/JavaMetadataExtractor.class","il/co/dcd/javaanalysis/JavaMetadataExtractor$1.class","il/co/dcd/javaanalysis/JavaMetadataExtractor$2.class",
            "il/co/dcd/javaanalysis/SourceSnapshot.class","il/co/dcd/composermapper/storage/XmlFactReader.class","il/co/dcd/composermapper/storage/SiblingPositions.class"))
            try(var input=FileFactReuse.class.getClassLoader().getResourceAsStream(resource)){if(input==null)throw new IllegalStateException("Missing analyzer policy resource: "+resource);hash.update(input.readAllBytes());}
        return HexFormat.of().formatHex(hash.digest());
    }
    FileFactReuse(AnalysisStore store,Path prior,boolean recovery,String policy)throws Exception {
        this.store=store;if(prior==null)return;
        Path database=prior.resolve("analysis/analysis.sqlite").toAbsolutePath().normalize();
        if(!Files.isRegularFile(database))throw new IllegalArgumentException("No previous analysis database: "+database);
        if(!recovery) {
            Path manifest=prior.resolve("vault-manifest.json");
            if(Files.exists(prior.resolve("vault-generation.json"))||!Files.isRegularFile(manifest)||Files.size(manifest)>65536)throw new IllegalArgumentException("Reuse requires a complete indexed map; use --resume-analysis for failed builder facts");
            var metadata=StoredJson.map(Files.readString(manifest));
            if(!Boolean.TRUE.equals(metadata.get("complete"))||!FileUtil.rawSha256(database).equals(metadata.get("analysis_hash")))throw new IllegalArgumentException("Previous analysis publication is not intact");
        }
        store.execute("ATTACH DATABASE ? AS previous",database.toUri()+"?mode=ro");attached=true;
        if(!policy.equals(store.scalar("SELECT value FROM previous.revision WHERE key='analysis_policy'"))) {
            store.commit();
            store.execute("DETACH DATABASE previous");attached=false;
            System.out.println("Previous analysis policy differs; source facts will be parsed with the current policy.");
        }
    }
    boolean copy(String path,String hash,String kind) {
        if(!attached||store.scalar("SELECT path FROM previous.files WHERE path=? AND hash=? AND complete=1",path,hash)==null)return false;
        if(kind.equals("JAVA")) {
            store.execute("INSERT INTO java_facts SELECT * FROM previous.java_facts WHERE file=?",path);
            store.execute("INSERT INTO java_classes SELECT * FROM previous.java_classes WHERE file=?",path);
        } else {
            store.execute("INSERT INTO xml_nodes SELECT * FROM previous.xml_nodes WHERE file=?",path);
            store.execute("INSERT INTO xml_attributes SELECT a.* FROM previous.xml_attributes a JOIN previous.xml_nodes n ON n.id=a.node WHERE n.file=?",path);
        }
        store.execute("UPDATE files SET complete=1 WHERE path=?",path);return true;
    }
    boolean edges(String path,String revision) {
        if(!attached||!revision.equals(store.scalar("SELECT value FROM previous.revision WHERE key='resolution_policy'")))return false;
        if(store.scalar("SELECT name FROM previous.sqlite_master WHERE type='table' AND name='java_resolution_ready'")==null)return false;
        if(store.scalar("SELECT f.path FROM files f JOIN previous.files p ON p.path=f.path AND p.hash=f.hash JOIN previous.java_resolution_ready r ON r.file=p.path WHERE f.path=?",path)==null)return false;
        store.execute("INSERT INTO java_edges SELECT * FROM previous.java_edges WHERE caller=?",path);
        store.execute("INSERT INTO records(collection,data) SELECT collection,data FROM previous.records WHERE collection='dependency_issues' AND json_extract(data,'$.file')=?",path);
        return true;
    }
    void finish(){if(attached){store.commit();store.execute("DETACH DATABASE previous");attached=false;}}
}
