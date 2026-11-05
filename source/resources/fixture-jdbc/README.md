# Converter-owned fixture JDBC release store

The explicit `fixture_jdbc_tools.py build-release` command populates
`releases/<version>/<bundle-id>` with tested driver/server binaries, wrappers
and evidence, and writes `installations/<bundle-id>.json`.

Distribute the selected release and its receipt with the converter. Local
build-populated binary/receipt directories are ignored by Git. Maintained
sources and distribution definitions remain tracked.

Future generation may locate and copy a pinned release. It must never generate,
compile, download or silently replace these tools. Copied tools require Java
only; fixture payloads stay in their separately referenced existing store.
