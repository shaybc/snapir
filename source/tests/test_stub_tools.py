from __future__ import annotations

from urllib.request import Request, urlopen

from models.conversion_models import RoutingPlan, RoutingStep
from tools.log_replay_tools.log_parser import parse_wsbcc_log
from tools.log_replay_tools.replay_case_builder import build_replay_cases
from tools.stub_tools.stub_generator import generate_stub_spec
from tools.stub_tools.stub_server import start_stub_server


def routing_plan() -> RoutingPlan:
    return RoutingPlan(
        operation_id="TransferFunds",
        channel="INTERNET",
        has_finally_step=False,
        steps=[
            RoutingStep(
                step_id="StepA",
                step_index=0,
                impl_class="com.bank.StepA",
                transitions={"0": "end", "4": "end", "8": 1},
            )
        ],
    )


def test_stub_generator_produces_one_scenario_per_routing_terminal_path():
    spec = generate_stub_spec("TransferFunds", [], routing_plan())

    assert [scenario["scenario"] for scenario in spec.scenarios] == ["success", "error_rc_4"]


def test_stub_server_returns_response_for_matching_request():
    spec = generate_stub_spec("TransferFunds", [], routing_plan())
    handle = start_stub_server(spec, 0)
    port = handle.server.server_address[1]
    try:
        request = Request(
            f"http://127.0.0.1:{port}/stub/TransferFunds/StepA/0",
            data=b"<request>StepA</request>",
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
    finally:
        handle.stop()

    assert "<returnCode>0</returnCode>" in body
    assert handle.get_call_log()[0]["path"] == "/stub/TransferFunds/StepA/0"


def test_log_parser_extracts_operation_name_and_xml(tmp_path):
    log_file = tmp_path / "wsbcc.log"
    log_file.write_text(
        "timestamp=2026-01-01T00:00:00Z operation_name=TransferFunds channel=INTERNET "
        "request_xml=<request><id>1</id></request> response_xml=<response><ok>true</ok></response>\n",
        encoding="utf-8",
    )

    entries = parse_wsbcc_log(str(log_file))

    assert entries[0]["operation_name"] == "TransferFunds"
    assert entries[0]["request_xml"] == "<request><id>1</id></request>"
    assert entries[0]["response_xml"] == "<response><ok>true</ok></response>"


def test_replay_case_builder_selects_success_and_error_cases():
    entries = [
        {
            "operation_name": "TransferFunds",
            "request_xml": "<request><id>1</id></request>",
            "response_xml": "<response><ok>true</ok></response>",
            "source_log_ref": "line-1",
        },
        {
            "operation_name": "TransferFunds",
            "request_xml": "<request><id>2</id></request>",
            "response_xml": "<ErrorResponse><code>4</code></ErrorResponse>",
            "source_log_ref": "line-2",
        },
    ]

    cases = build_replay_cases(entries, "TransferFunds")

    assert len(cases) == 2
    assert cases[0].source_log_ref == "line-1"
    assert cases[1].source_log_ref == "line-2"
