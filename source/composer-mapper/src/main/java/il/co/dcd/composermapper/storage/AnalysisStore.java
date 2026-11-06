package il.co.dcd.composermapper.storage;

import java.nio.file.*;
import java.sql.*;
import java.util.*;
import java.util.function.Function;

/** Bounded SQLite work/revision store. Queries are paged; compiler and XML trees are never retained. */
public final class AnalysisStore implements AutoCloseable {
    public final Connection connection;
    private int writes;
    private long writeBytes;
    private boolean closed;
    private final Map<String,PreparedStatement> statements=new LinkedHashMap<>(64,0.75f,true);

    public AnalysisStore(Path path) throws Exception {
        this(path,32);
    }
    public AnalysisStore(Path path,int cacheMib) throws Exception {
        Files.createDirectories(path.getParent());
        Class.forName("org.sqlite.JDBC");
        connection=DriverManager.getConnection("jdbc:sqlite:" + path.toAbsolutePath());
        try (var statement=connection.createStatement()) {
            statement.execute("PRAGMA cache_size=-"+(cacheMib*1024)); statement.execute("PRAGMA temp_store=FILE");
            statement.execute("PRAGMA journal_mode=WAL"); statement.execute("PRAGMA busy_timeout=5000");
        }
        connection.setAutoCommit(false);
        for (String sql : List.of(
            "CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,relative_path TEXT,channel TEXT,kind TEXT,hash TEXT,encoding TEXT,complete INTEGER DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS xml_nodes(id TEXT PRIMARY KEY,file TEXT,parent TEXT,ordinal INTEGER,type INTEGER,name TEXT,value TEXT,selector TEXT,owner TEXT,inside_format INTEGER DEFAULT 0,element_position INTEGER)",
            "CREATE INDEX IF NOT EXISTS xml_children ON xml_nodes(parent,ordinal)",
            "CREATE INDEX IF NOT EXISTS xml_element_positions ON xml_nodes(parent,element_position)",
            "CREATE INDEX IF NOT EXISTS xml_file ON xml_nodes(file)",
            "CREATE TABLE IF NOT EXISTS xml_attributes(node TEXT,name TEXT,value TEXT,PRIMARY KEY(node,name))",
            "CREATE TABLE IF NOT EXISTS java_facts(file TEXT,ordinal INTEGER,kind TEXT,name TEXT,value TEXT,extra TEXT,PRIMARY KEY(file,ordinal))",
            "CREATE INDEX IF NOT EXISTS java_fact_kind ON java_facts(file,kind,name)",
            "CREATE TABLE IF NOT EXISTS java_classes(file TEXT PRIMARY KEY,fqcn TEXT,package TEXT,simple_name TEXT,parent TEXT)",
            "CREATE INDEX IF NOT EXISTS java_class_names ON java_classes(fqcn)",
            "CREATE TABLE IF NOT EXISTS definitions(ordinal INTEGER PRIMARY KEY,kind TEXT,name TEXT,channel TEXT,file TEXT,relative_path TEXT,selector TEXT,owner TEXT,node TEXT)",
            "CREATE INDEX IF NOT EXISTS definition_names ON definitions(kind,name,channel)",
            "CREATE INDEX IF NOT EXISTS definition_owner ON definitions(kind,file,owner,ordinal)",
            "CREATE TABLE IF NOT EXISTS sets(collection TEXT,key TEXT,PRIMARY KEY(collection,key))",
            "CREATE TABLE IF NOT EXISTS records(collection TEXT,ordinal INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT)",
            "CREATE TABLE IF NOT EXISTS key_values(collection TEXT,key TEXT,data TEXT,PRIMARY KEY(collection,key))",
            "CREATE INDEX IF NOT EXISTS record_collections ON records(collection,ordinal)",
            "CREATE TABLE IF NOT EXISTS reservations(path TEXT PRIMARY KEY,owner TEXT,definition TEXT,channel TEXT,operation TEXT,operation_identity TEXT)",
            "CREATE TABLE IF NOT EXISTS notes(path TEXT PRIMARY KEY,definition TEXT,kind TEXT,entity_id TEXT,source_relative_path TEXT,source_selector TEXT,source_hash TEXT,channel TEXT,operation_id TEXT,operation_identity TEXT,usage_id TEXT,data TEXT,note_hash TEXT,body TEXT)",
            "CREATE INDEX IF NOT EXISTS note_definitions ON notes(definition)",
            "CREATE TABLE IF NOT EXISTS context_bindings(context TEXT,kind TEXT,key TEXT,note TEXT,PRIMARY KEY(context,kind,key))",
            "CREATE INDEX IF NOT EXISTS binding_note ON context_bindings(note)",
            "CREATE TABLE IF NOT EXISTS revision(key TEXT PRIMARY KEY,value TEXT)")) execute(sql);
        commit();
    }

    /** Write in bounded transactions; publication markers are a separate final operation. */
    public void execute(String sql,Object... arguments) {
        try {
            var statement=prepared(sql);
            bind(statement,arguments); statement.executeUpdate();
            for(Object argument:arguments)writeBytes+=argument instanceof String text?text.length()*2L:16;
            statement.clearParameters();
            if (++writes >= 500||writeBytes>=4L*1024*1024) commit();
        } catch (SQLException error) { throw new IllegalStateException(sql,error); }
    }

    public List<String[]> rows(String sql,Object... arguments) {
        return readRows(sql,false,arguments);
    }
    private List<String[]> pageRows(String sql,Object... arguments){return readRows(sql,true,arguments);}
    private List<String[]> readRows(String sql,boolean paged,Object...arguments) {
        List<String[]> result=new ArrayList<>();
        long bytes=0;
        try {
            var statement=prepared(sql);
            bind(statement,arguments);
            try (var cursor=statement.executeQuery()) {
                int columns=cursor.getMetaData().getColumnCount();
                while (cursor.next()) {
                    String[] row=new String[columns];long weight=0;
                    for(int i=0;i<columns;i++){row[i]=cursor.getString(i+1);weight+=row[i]==null?8:row[i].length()*2L+16;}
                    if(paged&&!result.isEmpty()&&bytes+weight>4L*1024*1024)break;
                    if(bytes+weight>16L*1024*1024)throw new IllegalStateException("SQL result exceeds bounded read budget: "+sql);
                    bytes+=weight;
                    result.add(row);
                    if (result.size()>10000) throw new IllegalStateException("Unbounded SQL query; use keyset pages: " + sql);
                }
            }
            statement.clearParameters();
        } catch(SQLException error) { throw new IllegalStateException(sql,error); }
        return result;
    }

    public String scalar(String sql,Object... arguments) {
        var result=rows(sql,arguments); return result.isEmpty() ? null : result.getFirst()[0];
    }

    /** A paged ordered relation compatible with existing stream-based consumers. */
    public <T> List<T> sequence(String from, String where, Object[] arguments, String fields, Function<String[],T> decode) {
        return new AbstractList<>() {
            @Override public int size() { return Integer.parseInt(scalar("SELECT count(*) FROM " + from + " WHERE " + where,arguments)); }
            @Override public T get(int index) {
                if(index<0) throw new IndexOutOfBoundsException(index);
                var page=rows("SELECT " + fields + " FROM " + from + " WHERE " + where + " ORDER BY ordinal LIMIT 1 OFFSET ?",append(arguments,index));
                if(page.isEmpty()) throw new IndexOutOfBoundsException(index); return decode.apply(page.getFirst());
            }
            @Override public Iterator<T> iterator() {
                return new Iterator<>() {
                    long after=-1; List<String[]> page=List.of(); int position;
                    private void fill() {
                        if(position < page.size()) return;
                        page=pageRows("SELECT ordinal,"+fields+" FROM "+from+" WHERE ("+where+") AND ordinal>? ORDER BY ordinal LIMIT 250",append(arguments,after));
                        position=0;
                    }
                    public boolean hasNext(){fill();return position<page.size();}
                    public T next(){if(!hasNext())throw new NoSuchElementException();var row=page.get(position++);after=Long.parseLong(row[0]);return decode.apply(Arrays.copyOfRange(row,1,row.length));}
                };
            }
            @Override public Spliterator<T> spliterator(){return Spliterators.spliteratorUnknownSize(iterator(),Spliterator.ORDERED);}
        };
    }

    public Set<String> set(String collection) {
        return new AbstractSet<>() {
            public int size(){return Integer.parseInt(scalar("SELECT count(*) FROM sets WHERE collection=?",collection));}
            public boolean contains(Object key){return scalar("SELECT key FROM sets WHERE collection=? AND key=?",collection,key)!=null;}
            public boolean add(String key){boolean fresh=!contains(key);if(fresh)execute("INSERT INTO sets VALUES (?,?)",collection,key);return fresh;}
            public Iterator<String> iterator(){return new Iterator<>() {
                String after=""; List<String[]> page=List.of();int position;
                private void fill(){if(position<page.size())return;page=rows("SELECT key FROM sets WHERE collection=? AND key>? ORDER BY key LIMIT 250",collection,after);position=0;}
                public boolean hasNext(){fill();return position<page.size();}
                public String next(){if(!hasNext())throw new NoSuchElementException();return after=page.get(position++)[0];}
            };}
        };
    }

    /** Persist contextual records rather than accumulating the global list in the service. */
    public List<Map<String,Object>> records(String collection) {
        var values=sequence("records","collection=?",new Object[]{collection},"data",row->StoredJson.map(row[0]));
        return new AbstractList<>() {
            public int size(){return values.size();}public Map<String,Object> get(int index){return values.get(index);}
            public Iterator<Map<String,Object>> iterator(){return values.iterator();}
            public Spliterator<Map<String,Object>> spliterator(){return values.spliterator();}
            public boolean add(Map<String,Object> value){execute("INSERT INTO records(collection,data) VALUES (?,?)",collection,StoredJson.encode(value));return true;}
        };
    }

    public void commit(){try{connection.commit();writes=0;writeBytes=0;}catch(SQLException e){throw new IllegalStateException(e);}}

    /** Bounded contextual memoization on disk, not one retained map per operation. */
    public Map<String,Map<String,Object>> mapping(String collection){return new AbstractMap<>() {
        public Map<String,Object> get(Object key){String data=scalar("SELECT data FROM key_values WHERE collection=? AND key=?",collection,key);return data==null?null:StoredJson.map(data);}
        public Map<String,Object> put(String key,Map<String,Object> value){var old=get(key);execute("INSERT OR REPLACE INTO key_values VALUES (?,?,?)",collection,key,StoredJson.encode(value));return old;}
        public Set<Entry<String,Map<String,Object>>> entrySet(){throw new UnsupportedOperationException("Use indexed contextual lookups");}
    };}
    public void checkpoint(){commit();try(var s=connection.createStatement()){connection.setAutoCommit(true);s.execute("PRAGMA wal_checkpoint(TRUNCATE)");connection.setAutoCommit(false);}catch(SQLException e){throw new IllegalStateException(e);}}
    public void close(){if(closed)return;commit();try{for(var statement:statements.values())statement.close();statements.clear();connection.close();closed=true;}catch(SQLException e){throw new IllegalStateException(e);}}
    private PreparedStatement prepared(String sql)throws SQLException {
        var statement=statements.get(sql);
        if(statement==null){if(statements.size()>=64){var oldest=statements.entrySet().iterator();oldest.next().getValue().close();oldest.remove();}statement=connection.prepareStatement(sql);statements.put(sql,statement);}
        statement.clearParameters();return statement;
    }
    private static void bind(PreparedStatement statement,Object[] arguments)throws SQLException{for(int i=0;i<arguments.length;i++)statement.setObject(i+1,arguments[i]);}
    private static Object[] append(Object[] values,Object last){var copy=Arrays.copyOf(values,values.length+1);copy[values.length]=last;return copy;}
}
