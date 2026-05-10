package il.co.dcd.composermapper;

import il.co.dcd.composermapper.index.*;
import il.co.dcd.composermapper.parser.*;
import il.co.dcd.composermapper.render.*;
import il.co.dcd.composermapper.service.*;
import il.co.dcd.composermapper.util.Args;
import java.nio.file.Path;

public class Main {
  public static void main(String[] args) {
    Args a = Args.parse(args);
    Path root = a.requiredPath("root");
    Path vault = a.requiredPath("vault");
    boolean clean = a.flag("clean", true);
    boolean markdownLinks = a.flag("md", false);

    FileDiscoveryService discovery = new FileDiscoveryService();
    var files = discovery.discover(root);

    Indexes indexes = new IndexBuildService().build(files);
    new VaultPreparationService().prepare(vault, clean);

    new StreamingGenerationService(
      new OperationFileParser(), new FormatFileParser(), new ContextFileParser(), new JavaClassParser(),
      new OperationMarkdownWriter(), new OpStepMarkdownWriter(), new FormatMarkdownWriter(),
      new ContextMarkdownWriter(), new JavaClassMarkdownWriter(), new LinkResolver(markdownLinks)
    ).generate(files, indexes, vault);

    System.out.println("Done. Ops=" + indexes.operationToSource().size() + ", steps=" + indexes.stepToSource().size() + ", formats=" + indexes.formatToSource().size() + ", contexts=" + indexes.contextToSource().size() + ", classes=" + indexes.classToSource().size());
  }
}
