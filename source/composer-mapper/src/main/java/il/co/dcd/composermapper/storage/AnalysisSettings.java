package il.co.dcd.composermapper.storage;

import il.co.dcd.composermapper.util.Args;
import java.util.Map;

/** Explicit analysis budgets; user tuning cannot disable the protocol's memory ceilings. */
public record AnalysisSettings(int batchFiles,int batchBytes,int javaFileBytes,int sqliteCacheMib) {
    public static AnalysisSettings defaults(){return new AnalysisSettings(100,4*1024*1024,8*1024*1024,32);}
    public static AnalysisSettings from(Args args){return new AnalysisSettings(value(args,"analysis-batch-files",100,100),value(args,"analysis-batch-mib",4,4)*1024*1024,value(args,"analysis-java-file-mib",8,8)*1024*1024,value(args,"analysis-sqlite-cache-mib",32,32));}
    private static int value(Args args,String name,int fallback,int maximum){String text=args.optional(name);int value=text==null?fallback:Integer.parseInt(text);if(value<1||value>maximum)throw new IllegalArgumentException("--"+name+" must be between 1 and "+maximum);return value;}
    public Map<String,Object> metadata(){return Map.of("batch_files",batchFiles,"batch_decoded_bytes",batchBytes,"java_file_bytes",javaFileBytes,"sqlite_cache_mib",sqliteCacheMib,"query_page_rows",250,"query_page_bytes",4*1024*1024,"record_bytes",4*1024*1024,"xml_depth",512,"java_workers",1);}
}
