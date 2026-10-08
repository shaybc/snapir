package il.co.dcd.composermapper.service;

import java.nio.file.Path; import java.util.*;

public class ProcessingReport {
  private final Map<Path,String> failedXmlFiles=new LinkedHashMap<>();
  public void recordXmlFailure(Path path, Exception e){ failedXmlFiles.putIfAbsent(path, rootMessage(e)); }
  public boolean hasXmlFailure(Path path){ return failedXmlFiles.containsKey(path); }
  public Map<Path,String> failedXmlFiles(){ return Collections.unmodifiableMap(failedXmlFiles); }
  public boolean hasFailures(){ return !failedXmlFiles.isEmpty(); }
  private String rootMessage(Throwable e){ Throwable t=e; while(t.getCause()!=null) t=t.getCause(); return t.getClass().getSimpleName()+": "+String.valueOf(t.getMessage()); }
}
