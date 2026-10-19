"""Bound operation review evidence while retaining every source and test."""

from copy import deepcopy

from runtime.behavior_conversion.request_context import encode_request


def review_requests(payload, instruction, schema, limit):
    """Deduplicate accepted contracts, then pack whole tests into bounded review parts.

    Each part retains the complete service, original routing, accepted APIs and metadata.
    Every test is reviewed; no source text is truncated. Oversized indivisible evidence
    fails explicitly. The input and accepted artifacts are never modified.
    """
    result = deepcopy(payload)
    bundle = result.get("bundle", {})
    contract = bundle.get("operation_contract") or {}
    if not contract:
        return [result]
    units = contract.get("units", [])
    references = False
    for accepted in result.get("accepted_units", {}).values():
        for index, unit in enumerate(units):
            if accepted.get("contract") == unit:
                accepted.pop("contract")
                accepted["contract_ref"] = f"bundle.operation_contract.units[{index}]"
                references = True
                for field in ("apis", "input_type", "output_type", "wire_type"):
                    if field in accepted and accepted[field] == unit.get(field):
                        accepted.pop(field)
                        accepted[field + "_ref"] = f"bundle.operation_contract.units[{index}].{field}"
                break
    if references:
        result["review_evidence_references"] = (
            "Fields ending in _ref refer to exact retained values at the named JSON path in this request. "
            "All accepted contracts and APIs remain present in bundle.operation_contract.units.")
    def fits(request):
        try:
            encode_request(dict(request, schema=schema), instruction, limit)
            return True
        except ValueError as exc:
            if "context budget" not in str(exc):
                raise
            return False
    if fits(result):
        return [result]
    tests = [file for file in bundle.get("files", []) if file["path"].startswith("src/test/java/")]
    main = [file for file in bundle.get("files", []) if file not in tests]
    def part(files):
        selected = {file["path"] for file in files}
        current = deepcopy(result)
        current["bundle"]["files"] = main + files
        current["bundle"]["coverage"] = {key: [path for path in paths if path in selected]
            for key, paths in bundle.get("coverage", {}).items() if any(path in selected for path in paths)}
        current["review_scope"] = dict(test_files=sorted(selected), all_test_files=[file["path"] for file in tests],
            instruction="Review the full service and routing, and only the supplied test subset. Other listed tests are reviewed in separate parts; their absence here is not missing coverage.")
        return current
    # Test with conservatively wide part numbers so the final metadata cannot overflow.
    def bounded(files):
        return fits(dict(part(files), review_part=999999, review_parts=999999))
    if not tests or not bounded([]):
        raise ValueError("Behavior review service and routing evidence exceeds its context budget even without tests")
    groups, current = [], []
    for file in tests:
        if not bounded(current + [file]):
            if current:
                groups.append(current)
            current = []
        if not bounded([file]):
            raise ValueError("Behavior review test exceeds its context budget: " + file["path"])
        current.append(file)
    if current:
        groups.append(current)
    return [dict(part(files), review_part=index + 1, review_parts=len(groups))
            for index, files in enumerate(groups)]
