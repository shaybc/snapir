package il.co.dcd.composermapper.render;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.JavaClassDef;
import il.co.dcd.composermapper.service.LinkResolver;
import il.co.dcd.composermapper.util.FileUtil;
import il.co.dcd.composermapper.util.SafePathNames;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Set;

public class JavaClassMarkdownWriter {
  public void write(JavaClassDef j, Indexes x, LinkResolver links, Path vault) {
    Path out = vault.resolve(SafePathNames.classPathWithoutExtension(j.getFullyQualifiedName()) + ".md");
    StringBuilder sb = new StringBuilder();

    sb.append("# ").append(j.getFullyQualifiedName())
        .append("\n\n---\nentity_type: java_class\nentity_id: ").append(j.getFullyQualifiedName())
        .append("\nconversion_status: not_started\n")
        .append("shared: ").append(isShared(j, x)).append("\n")
        .append(MarkdownSupport.usedByList("used_by_steps", x.classUsedBySteps().get(j.getFullyQualifiedName())))
        .append("source_file: ").append(j.getSourceFile())
        .append("\nsource_hash: ").append(FileUtil.sha256(j.getSourceFile()))
        .append("\n---\n\n## Package\n");

    sb.append(MarkdownSupport.bullet(MarkdownSupport.code(j.getPackageName())));

    sb.append("\n## Behavior Type\n");
    if (j.getBehaviorTypes().isEmpty()) {
      sb.append("- unknown\n");
    } else {
      j.getBehaviorTypes().forEach(t -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(t))));
    }

    appendIbmDependencyWarning(sb, j);

    sb.append("\n## Return Codes\n");
    if (j.getReturnCodes().isEmpty()) {
      sb.append("- None\n");
    } else {
      j.getReturnCodes().values().forEach(code -> sb.append(MarkdownSupport.bullet(returnCodeText(code))));
    }

    sb.append("\n## Thrown Exceptions\n");
    if (j.getThrownExceptions().isEmpty()) {
      sb.append("- None\n");
    } else {
      j.getThrownExceptions().forEach(e -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(e))));
    }

    sb.append("\n## Methods\n");
    if (j.getMethodNames().isEmpty()) {
      sb.append("- None\n");
    } else {
      j.getMethodNames().forEach(m -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(m))));
    }

    sb.append("\n## Setter Methods\n");
    if (j.getSetterNames().isEmpty()) {
      sb.append("- None\n");
    } else {
      j.getSetterNames().forEach(m -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(m))));
    }

    sb.append("\n## Imports\n");
    if (j.getImports().isEmpty()) {
      sb.append("- None\n");
    } else {
      j.getImports().forEach(i -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(i))));
    }

    sb.append("\n## Inferred External Dependencies\n");
    if (j.getInferredExternalDependencies().isEmpty()) {
      sb.append("- None\n");
    } else {
      j.getInferredExternalDependencies().forEach(d -> sb.append(MarkdownSupport.bullet(d)));
    }

    try {
      FileUtil.writeString(out, sb.toString());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  private String returnCodeText(JavaClassDef.ReturnCode code) {
    if (code.getMeanings().isEmpty()) return "Returns " + MarkdownSupport.code(code.getCode());
    return "Returns " + MarkdownSupport.code(code.getCode()) + " (" + String.join("; ", code.getMeanings()) + ")";
  }

  private void appendIbmDependencyWarning(StringBuilder sb, JavaClassDef j) {
    if (!j.getInferredExternalDependencies().contains("IBM/WAS")) return;

    sb.append("\n## IBM Dependency Warning\n")
        .append("- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.\n");
    j.getImports().stream()
        .filter(i -> i.equals("com.ibm") || i.startsWith("com.ibm."))
        .forEach(i -> sb.append(MarkdownSupport.bullet(MarkdownSupport.code(i))));
  }

  private boolean isShared(JavaClassDef j, Indexes x) {
    Set<String> steps = x.classUsedBySteps().get(j.getFullyQualifiedName());
    return steps != null && steps.size() > 1;
  }
}
