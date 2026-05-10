# Composer Mapper

This version is designed for large Composer/WSBCC repos.

Flow:
1. Discover XML / INI / Java files
2. Build lightweight indexes only
3. Parse one source file at a time
4. Write markdown immediately
5. Discard parsed objects and move on

Output:
- operations/
- opsteps/
- formats/
- contexts/
- classes/<package path>/
- analysis/unresolved-references.md

## Minimum install requirements

- Java 17 or newer
- Apache Maven 3.8 or newer
- Access to Maven Central on the first build, so Maven can download build plugins
- An IBM Composer code base containing XML, INI, and/or Java files
- A writable output folder for the generated documentation tree

Check local versions:

```bash
java -version
mvn -version
```

## Compile the project

From the project root:

```bash
mvn clean package
```

This compiles the Java sources and creates the runnable jar:

```text
target/composer-mapper-1.1.1-jar-with-dependencies.jar
```

## Run tests

From the project root:

```bash
mvn test
```

The current project has no test sources yet, but this command still verifies that the project compiles successfully through Maven's test lifecycle.

## Generate a document tree with standard Markdown links

Use this mode when the generated documentation will be viewed in a regular Markdown renderer, Git repository browser, static site generator, or any tool that expects links like `[GetClientLinksOp](operations/GetClientLinksOp.md)`.

```bash
java -jar target/composer-mapper-1.1.1-jar-with-dependencies.jar --root "C:\code\ibm-composer" --vault "C:\docs\composer-map" --md
```

Arguments:
- `--root` points to the IBM Composer code base to scan.
- `--vault` points to the output folder where the generated Markdown document tree will be written.
- `--md` switches generated cross-references from Obsidian wiki links to standard Markdown links.

The output folder will contain the generated document tree:
- `operations/`
- `opsteps/`
- `formats/`
- `contexts/`
- `classes/`
- `analysis/unresolved-references.md`

## Generate an Obsidian vault with wiki links

Use this mode when the generated documentation will be opened directly as an Obsidian vault. This is the default behavior and produces links like `[[operations/GetClientLinksOp|GetClientLinksOp]]`.

```bash
java -jar target/composer-mapper-1.1.1-jar-with-dependencies.jar --root "C:\code\ibm-composer" --vault "C:\obsidian\vaults\composer-map"
```

Arguments:
- `--root` points to the IBM Composer code base to scan.
- `--vault` points to the Obsidian vault folder where the generated notes will be written.
- Omit `--md` to keep the default Obsidian wiki-link format.
