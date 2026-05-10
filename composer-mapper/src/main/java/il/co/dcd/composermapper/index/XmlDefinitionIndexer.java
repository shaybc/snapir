package il.co.dcd.composermapper.index;
import il.co.dcd.composermapper.util.XmlUtil; import org.w3c.dom.*; import java.nio.file.Path; import java.util.*;
public class XmlDefinitionIndexer {
  public void index(Path xmlFile, Indexes x){ walk(XmlUtil.parse(xmlFile).getDocumentElement(), xmlFile, x, null); }
  private void walk(Element e, Path xml, Indexes x, String currentOp){ switch(e.getTagName()){
    case "CCDSEServerOperation" -> { String id=XmlUtil.attr(e,"id"); if(id!=null&&!id.isBlank()){ x.operationToSource().put(id,xml); String ctx=XmlUtil.attr(e,"operationContext"); if(ctx!=null&&!ctx.isBlank()) x.operationToContext().put(id,ctx); currentOp=id; } }
    case "opStep" -> { String id=XmlUtil.attr(e,"id"); if(id!=null&&!id.isBlank()){ x.stepToSource().put(id,xml); if(currentOp!=null) x.stepToOperation().put(id,currentOp); String impl=XmlUtil.attr(e,"implClass"); if((impl==null||impl.isBlank())&&x.tagToClass().containsKey("opStep")) impl=x.tagToClass().get("opStep"); if(impl!=null&&!impl.isBlank()){ x.stepToImplClass().put(id,impl); x.classUsedBySteps().computeIfAbsent(impl,k->new LinkedHashSet<>()).add(id);} } }
    case "fmtDef" -> { String id=XmlUtil.attr(e,"id"); if(id!=null&&!id.isBlank()) x.formatToSource().put(id,xml); }
    case "context" -> { String id=XmlUtil.attr(e,"id"); if(id!=null&&!id.isBlank()) x.contextToSource().put(id,xml); }
    case "refFormat" -> { if(currentOp!=null){ String ref=XmlUtil.attr(e,"refid"); if(ref!=null&&!ref.isBlank()){ x.operationToFormats().computeIfAbsent(currentOp,k->new LinkedHashSet<>()).add(ref); x.formatUsedByOperations().computeIfAbsent(ref,k->new LinkedHashSet<>()).add(currentOp); } } }
  }
  for(Element c:XmlUtil.childElements(e)) walk(c,xml,x,currentOp);
  }
  public void finalizeUnresolved(Indexes x){ for(var v:x.operationToFormats().values()) for(String f:v) if(!x.formatToSource().containsKey(f)) x.unresolvedFormatRefs().add(f); for(String c:x.operationToContext().values()) if(!x.contextToSource().containsKey(c)) x.unresolvedContextRefs().add(c); for(String cls:x.stepToImplClass().values()) if(!x.classToSource().containsKey(cls)) x.unresolvedClassRefs().add(cls); }
}
