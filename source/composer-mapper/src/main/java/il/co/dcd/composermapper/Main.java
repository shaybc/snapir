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

        Path root    = a.requiredPath("root");
        Path vault   = a.requiredPath("vault");
        boolean clean         = a.flag("clean", true);
        boolean markdownLinks = a.flag("md", false);
        String  channel       = a.optional("channel");   // null if not provided

        FileDiscoveryService discovery = new FileDiscoveryService();
        var files = discovery.discover(root, channel);
        ProcessingReport report = new ProcessingReport();

        String layout = a.optional("vault-layout");
        if (layout != null && !layout.equals("legacy") && !layout.equals("scoped"))
            throw new IllegalArgumentException("--vault-layout must be legacy or scoped");
        if ("scoped".equals(layout)) {
            try {
                new ScopedVaultGenerationService().generate(root, vault, files, channel,
                    a.optional("workspace-id"), markdownLinks, report);
            } catch (java.io.IOException e) {
                throw new RuntimeException("Failed generating scoped vault", e);
            }
            if (report.hasFailures()) throw new IllegalStateException("Scoped vault has source parsing failures; inspect manifest diagnostics");
            System.out.println("Done. Scoped vault manifest: " + vault.resolve("vault-manifest.json"));
            return;
        }

        var legacyCollisions = LegacyVaultCollisionCheck.find(root, files, report);
        legacyCollisions.forEach(System.err::println);
        Indexes indexes = new IndexBuildService().build(files, report);
        new VaultPreparationService().prepare(vault, clean);

        new StreamingGenerationService(
            new OperationFileParser(), new FormatFileParser(),
            new ContextFileParser(),   new JavaClassParser(),
            new OperationMarkdownWriter(), new OpStepMarkdownWriter(),
            new FormatMarkdownWriter(),    new ContextMarkdownWriter(),
            new JavaClassMarkdownWriter(), new LinkResolver(markdownLinks)
        ).generate(files, indexes, vault, report);

        if (!legacyCollisions.isEmpty()) {
            try {
                il.co.dcd.composermapper.util.FileUtil.writeString(vault.resolve("analysis/entity-collisions.md"),
                    "# Legacy identity collisions\n\nThese source occurrences cannot be represented independently in the legacy layout.\n\n"
                    + String.join("\n", legacyCollisions.stream().map(value -> "- " + value).toList()) + "\n");
            } catch (java.io.IOException e) {
                throw new RuntimeException("Failed recording legacy collisions", e);
            }
        }

        System.out.println("Done."
            + " ops="      + indexes.operationToSource().size()
            + " steps="    + indexes.stepToSource().size()
            + " formats="  + indexes.formatToSource().size()
            + " contexts=" + indexes.contextToSource().size()
            + " classes="  + indexes.classToSource().size()
            + " channels=" + indexes.channelForOperation().values().stream().distinct().count());

        if (channel != null)
            System.out.println("Channel filter: " + channel);

        if (report.hasFailures()) {
            System.out.println("XML files that failed parsing:");
            report.failedXmlFiles().forEach((file, error) ->
                System.out.println("- " + file + " (" + error + ")"));
        }
    }
}
