"""Exercise runtime-test orchestration without claiming real requests were executed."""

import json
import logging
from pathlib import Path


class DummyRuntimeTestExecutor:
    """Return successful test results using the future runtime executor boundary."""

    def test_xml_compatibility(self, operation):
        """Return dummy success without sending an XML request."""
        return True

    def test_behavioral_equivalence(self, operation):
        """Return dummy success without comparing business behavior."""
        return True

    def test_legacy_trace_comparison(self, operation):
        """Return dummy success without capturing legacy or service traces."""
        return True

    def execute(self, operation, directory):
        """Persist the success-shaped report with unmistakable dummy provenance."""
        directory = Path(directory).resolve()
        output = directory / "reports" / "6_service_generation_and_validation" / "runtime_test_reports" / operation["channel"] / operation["operation_id"] / "report.json"
        if not output.resolve().is_relative_to(directory):
            raise ValueError("Runtime test report is outside the run workspace")
        checks = dict(xml_compatibility=self.test_xml_compatibility(operation),
                      behavioral_equivalence=self.test_behavioral_equivalence(operation),
                      legacy_trace_comparison=self.test_legacy_trace_comparison(operation))
        report = dict(executor="dummy", simulated=True, real_tests_executed=False,
                      notice="Dummy runtime tests always return success. Real endpoint tests are not implemented.",
                      operation_id=operation["operation_id"], channel=operation["channel"], checks=checks)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
        logging.getLogger(__name__).warning("Dummy runtime validation for %s/%s: no real tests executed",
                                            operation["channel"], operation["operation_id"])
        return {**{name: "passed" if passed else "failed" for name, passed in checks.items()},
                "runtime_test_executor": "dummy", "runtime_tests_simulated": True,
                "runtime_validation_notice": report["notice"],
                "evidence_paths": {name: [str(output.relative_to(directory))] for name in checks}}
