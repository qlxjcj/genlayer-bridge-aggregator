"""Direct-mode tests for Bridge Aggregator."""

import json

from conftest import (
    LLM_PATTERN,
    LLM_RESPONSE_BEST,
    LLM_RESPONSE_FAIL,
    with_bridge_data,
)


def test_find_best_route(aggregator):
    vm, c = aggregator
    qid = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    assert c.get_quote_count() == 1
    raw = c.get_quote(qid)
    q = json.loads(raw)
    assert q["best_bridge"] == "across"
    assert float(q["best_fee"]) == 0.3


def test_returns_quote_id(aggregator):
    vm, c = aggregator
    qid = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    assert qid == "1"
    raw = c.get_quote(qid)
    assert raw != "{}"


def test_cross_validation_pass(aggregator):
    vm, c = aggregator
    qid = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    raw = c.get_quote(qid)
    q = json.loads(raw)
    assert q["cross_validation"] == "PASS"


def test_provider_specific_urls(aggregator):
    vm, c = aggregator
    qid = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    raw = c.get_quote(qid)
    q = json.loads(raw)
    all_quotes = json.loads(q["all_quotes"])
    assert "stargate" in all_quotes
    assert "across" in all_quotes


def test_supported_bridges(aggregator):
    vm, c = aggregator
    bridges = c.get_supported_bridges()
    assert "stargate" in bridges
    assert "across" in bridges


def test_concurrent_requests(aggregator):
    vm, c = aggregator
    qid1 = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    qid2 = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    assert qid1 != qid2
    assert c.get_quote_count() == 2


def test_all_bridges_failed(aggregator):
    vm, c = aggregator
    vm.clear_mocks()
    vm.mock_web(".*stargate.*", {"method": "GET", "status": 200, "body": ""})
    vm.mock_web(".*hop.*", {"method": "GET", "status": 200, "body": ""})
    vm.mock_web(".*across.*", {"method": "GET", "status": 200, "body": ""})
    vm.mock_web(".*cbridge.*", {"method": "GET", "status": 200, "body": ""})
    vm.mock_llm(LLM_PATTERN, LLM_RESPONSE_FAIL)
    qid = c.find_best_route("ethereum", "polygon", "USDC", "1000")
    raw = c.get_quote(qid)
    q = json.loads(raw)
    assert q["cross_validation"] == "FAIL"


def test_requires_params(aggregator):
    vm, c = aggregator
    try:
        c.find_best_route("", "polygon", "USDC", "1000")
        assert False, "Should have raised"
    except Exception:
        pass


def test_stats(aggregator):
    vm, c = aggregator
    c.find_best_route("ethereum", "polygon", "USDC", "1000")
    s = c.get_stats()
    assert s["total"] == 1
    assert s["cross_validated"] == 1
