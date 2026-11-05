# Huge Bank Demo

From the repository root, generate the default local fixture:

```powershell
.\.venv\Scripts\python.exe -B source/generate_huge_bank_demo.py
```

The generated `huge-bank-demo/` folder is ignored by Git. The generator and its
documentation are tracked. Generation requires only Python's standard library;
it does not call an AI model, download dependencies, or run the mapper.

`--files` is a **minimum total fixture file count**, including the copied seed
and manifest. Complete families are generated, so the actual count can exceed
the target. With the current seed, the default creates **1,012 files: 480 operation
XML files, 2,688 inline OP-step occurrences, and 513 Java files**, plus shared
configuration and documentation. An OP-step occurrence is an XML node, not a
separate file; its implementation is an existing or copied Java source file.

Grow the same folder later without deleting it or changing previous families:

```powershell
.\.venv\Scripts\python.exe -B source/generate_huge_bank_demo.py --files 5000
.\.venv\Scripts\python.exe -B source/generate_huge_bank_demo.py --files 22000
```

Repeating a target already reached makes no changes. A smaller target does not
shrink the fixture. `huge-bank-demo.json` records the actual counts and seed
fingerprint. If the seed changes, use a new `--output` folder. An unrelated
existing output folder is rejected; the generator never deletes directories.
Custom output folders are not covered by the default Git ignore entry.

Each family copies all ten operation documents across INTERNET and IVR, using
suffixes such as `Huge00001`. Nested-operation calls target the same family's
copied operations. Inline format identities, OP-step identities and transition
targets are renamed consistently; request/reply payload names and context fields
remain unchanged. Common validation/error steps, contexts, external formats,
framework code, database procedure names and service names remain shared.
Channel-specific Java steps are copied with renamed classes and unchanged business
statements. Alternating step occurrences use either these copies or the original
implementations, producing both private dependencies and cross-operation sharing.
The original operations are retained too.

## Converter configuration

Create a new configuration through `run.cmd` or `run-verbose.cmd`:

- Source workspace: `<repo>/huge-bank-demo/composer/Workspace`.
- Use a distinct workspace identity, such as `huge-bank-demo`.
- Create a new Composer map for this workspace; the small seed's map does not
  describe the generated operations. An existing map must have been generated
  from this huge workspace.
- Channels: `INTERNET`, `IVR`, or just the channel being tested.
- For a segmented test, include `GetClientOverviewOpHuge00001`. Its prerequisites
  are `ValidateClientLinksOpHuge00001` and `GetClientLinksOpHuge00001`.
- For a single database operation, include `GetAccountDetailsOpHuge00001`.

Use separate migration run directories for cold and warm measurements. Record
`logs/intake.log`, `logs/intake-progress.json`, and any `logs/intake-stacks.log`.
Increasing the fixture requires a new map or map regeneration before comparing
the larger workload. Existing database/service prerequisites and the seed's
documented behavior, limitations and deliberately seeded defects remain intact.
This fixture stresses repeated operations and source discovery; it does not model
thousands of independently different business algorithms or enterprise classpaths.
