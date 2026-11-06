package il.co.dcd.composermapper.storage;

import java.util.*;

/** Keep ordinary tag counters small; spill unusual wide XML vocabularies to SQLite. */
final class SiblingPositions {
    private final AnalysisStore store;private final String parent;
    private final Map<String,Integer> counts=new HashMap<>();private int bytes;private boolean spilled;
    SiblingPositions(AnalysisStore store,String parent){this.store=store;this.parent=parent;}
    int next(String tag) {
        if(!spilled) {
            if(counts.containsKey(tag))return counts.merge(tag,1,Integer::sum);
            int weight=tag.length()*2+64;
            if(counts.size()<128&&bytes+weight<=8192){bytes+=weight;counts.put(tag,1);return 1;}
            store.execute("CREATE TEMP TABLE IF NOT EXISTS sibling_positions(parent TEXT,tag TEXT,count INTEGER,PRIMARY KEY(parent,tag))");
            counts.forEach((name,count)->store.execute("INSERT INTO sibling_positions VALUES (?,?,?)",parent,name,count));counts.clear();spilled=true;
        }
        store.execute("INSERT INTO sibling_positions VALUES (?,?,1) ON CONFLICT(parent,tag) DO UPDATE SET count=count+1",parent,tag);
        return Integer.parseInt(store.scalar("SELECT count FROM sibling_positions WHERE parent=? AND tag=?",parent,tag));
    }
    void close(){if(spilled)store.execute("DELETE FROM sibling_positions WHERE parent=?",parent);}
}
