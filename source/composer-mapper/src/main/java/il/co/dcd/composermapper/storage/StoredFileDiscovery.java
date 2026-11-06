package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.model.DiscoveredFile;
import il.co.dcd.composermapper.service.ChannelImportResolver;
import java.nio.file.*;
import java.util.*;

/** Enumerate captured file metadata through indexed pages, with existing Java channel ownership. */
final class StoredFileDiscovery {
    static List<DiscoveredFile> discover(AnalysisSession session,String channel) {
        AnalysisStore store=session.store;
        store.execute("CREATE TEMP TABLE IF NOT EXISTS source_channels(root TEXT,channel TEXT,PRIMARY KEY(root,channel))");
        for(var row:store.rows("SELECT path,channel FROM files WHERE lower(relative_path) LIKE '%/dse.ini' LIMIT 10000")) {
            Path channels=Path.of(row[0]).getParent().getParent(),definitions=channels==null?null:channels.getParent(),source=definitions==null?null:definitions.getParent();
            if(source!=null&&channels.getFileName().toString().equalsIgnoreCase("Channel")&&definitions.getFileName().toString().equalsIgnoreCase("Xml Definition")&&source.getFileName().toString().equalsIgnoreCase("src"))store.execute("INSERT OR IGNORE INTO source_channels VALUES (?,?)",source.toString(),row[1]);
        }
        store.execute("UPDATE files SET channel=(SELECT channel FROM source_channels c WHERE substr(files.path,1,length(c.root)+1)=c.root||? AND (SELECT count(*) FROM source_channels x WHERE x.root=c.root)=1 ORDER BY length(c.root) DESC LIMIT 1) WHERE kind='JAVA' AND channel IS NULL",java.io.File.separator);
        store.execute("CREATE TEMP VIEW IF NOT EXISTS discovered_files AS SELECT rowid AS ordinal,path,kind,channel,relative_path FROM files WHERE kind='JAVA' OR lower(relative_path) LIKE '%.ini' OR (lower(relative_path) LIKE '%.xml' AND lower(relative_path) NOT LIKE '%/pom.xml' AND lower(relative_path)<>'pom.xml')");
        String clause="1=1";Object[] arguments={};
        if(channel!=null&&!channel.isBlank()) {
            var allowed=new ChannelImportResolver().resolve(values(store,clause,arguments),channel);
            clause="channel IS NULL OR upper(channel) IN ("+String.join(",",Collections.nCopies(allowed.size(),"?"))+")";arguments=allowed.toArray();
        }
        return values(store,clause,arguments);
    }
    private static List<DiscoveredFile> values(AnalysisStore store,String clause,Object[] args){return store.sequence("discovered_files",clause,args,"path,kind,channel",row->new DiscoveredFile(Path.of(row[0]),row[1].equals("JAVA")?DiscoveredFile.FileType.JAVA:row[0].toLowerCase(Locale.ROOT).endsWith(".ini")?DiscoveredFile.FileType.INI:DiscoveredFile.FileType.XML,row[2]));}
}
