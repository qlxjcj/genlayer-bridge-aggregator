"""Shared fixtures and mocks for Bridge Aggregator tests."""

import json
import os
import pytest

CONTRACT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "bridge_aggregator.py",
)

LLM_PATTERN = r".*bridge.*aggregator.*|.*best_bridge.*|.*all_quotes.*"

STARGATE_QUOTE = json.dumps({"fee": "0.5", "time": "5", "output": "999.5"})
HOP_QUOTE = json.dumps({"fee": "0.8", "time": "10", "output": "999.2"})
ACROSS_QUOTE = json.dumps({"fee": "0.3", "time": "3", "output": "999.7"})
CBRIDGE_QUOTE = json.dumps({"fee": "0.6", "time": "8", "output": "999.4"})

LLM_RESPONSE_BEST = json.dumps({
    "all_quotes": {
        "stargate": {"fee": "0.5", "time": "5", "output": "999.5"},
        "hop": {"fee": "0.8", "time": "10", "output": "999.2"},
        "across": {"fee": "0.3", "time": "3", "output": "999.7"},
        "cbridge": {"fee": "0.6", "time": "8", "output": "999.4"}
    },
    "best_bridge": "across",
    "best_fee": "0.3",
    "best_time": "3",
    "best_output": "999.7",
    "cross_validation": "PASS",
    "source_agreement": "85",
    "reasoning": "Across has lowest fee and fastest time."
})

LLM_RESPONSE_FAIL = json.dumps({
    "all_quotes": {},
    "best_bridge": "none",
    "best_fee": "0",
    "best_time": "0",
    "best_output": "0",
    "cross_validation": "FAIL",
    "source_agreement": "0",
    "reasoning": "No bridge data retrieved."
})


def with_bridge_data(vm):
    vm.mock_web(".*stargate.*", {"method": "GET", "status": 200, "body": STARGATE_QUOTE})
    vm.mock_web(".*hop.*", {"method": "GET", "status": 200, "body": HOP_QUOTE})
    vm.mock_web(".*across.*", {"method": "GET", "status": 200, "body": ACROSS_QUOTE})
    vm.mock_web(".*cbridge.*", {"method": "GET", "status": 200, "body": CBRIDGE_QUOTE})
    vm.mock_llm(LLM_PATTERN, LLM_RESPONSE_BEST)


@pytest.fixture
def aggregator(direct_vm, direct_deploy):
    vm = direct_vm
    c = direct_deploy(CONTRACT)
    with_bridge_data(vm)
    return vm, c
