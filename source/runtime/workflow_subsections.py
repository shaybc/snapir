"""Short subsection titles for the seven migration stages."""


SUBSECTIONS = {
    "intake_and_legacy_analysis": [
        ("discover", "Discover", [("sources", "Java sources"), ("classpath", "Classpath")]),
        ("inventory", "Map components", [("definitions", "Definitions"), ("usage", "Usage and dependencies")]),
        ("mapper", "Run mapper", []),
        ("analysis", "Analyze legacy code", []),
        ("contexts", "Prepare inputs", [("hierarchies", "Context hierarchies"), ("scope", "Operation scope")]),
    ],
    "migration_planning": [
        ("scope", "Load scope", []),
        ("plan", "Create plan", [("generate", "Generate"), ("validate", "Validate")]),
        ("ownership", "Plan libraries", []),
        ("report", "Write report", []),
        ("approval", "Approve plan", []),
    ],
    "dependency_closure_and_component_conversion": [
        ("closure", "Check dependencies", []),
        ("units", "Collect units", []),
        ("convert", "Convert units", []),
        ("report", "Write results", []),
    ],
    "component_review": [
        ("gather", "Gather evidence", []),
        ("review", "Review components", []),
        ("build", "Check builds", []),
        ("report", "Write report", []),
        ("approval", "Approve components", []),
    ],
    "operation_assembly_and_review": [
        ("gather", "Gather", [("units", "Accepted units"), ("routing", "Original routing")]),
        ("generate", "Generate", [("service", "Operation service")]),
        ("validate", "Validate and compile", [("json", "JSON and files"), ("interfaces", "Accepted interfaces"), ("compile", "Compile")]),
        ("plan", "Plan tests", [("generate", "Create scenarios"), ("coverage", "Check original routes")]),
        ("scenarios", "Test scenarios", []),
        ("suite", "Run all tests", []),
        ("review", "Review", [("behavior", "Compare behavior"), ("report", "Write report"), ("approval", "Approve operation")]),
    ],
    "service_generation_and_validation": [
        ("gather", "Gather approved code", []),
        ("generate", "Generate service", [("wrappers", "HTTP and XML wrappers"), ("dependencies", "Dependencies and files")]),
        ("validate", "Validate service", [("guard", "Framework check"), ("compile", "Compile"), ("test", "Tests"), ("package", "Package")]),
        ("runtime", "Check behavior", [("xml", "XML compatibility"), ("equivalence", "Behavior comparison")]),
        ("report", "Write results", []),
    ],
    "final_validation": [
        ("evidence", "Check evidence", []),
        ("delivery", "Prepare delivery", [("deployment", "Deployment files"), ("docs", "Documentation")]),
        ("report", "Write final report", []),
        ("approval", "Approve migration", []),
    ],
}
