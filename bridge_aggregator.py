# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import json
from dataclasses import dataclass
from genlayer import *


BRIDGE_ADAPTERS = {
    "stargate": {
        "url": "https://api.stargate.finance/quote",
        "chain_ids": {"ethereum": "1", "polygon": "137", "arbitrum": "42161", "optimism": "10"},
        "token_ids": {"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7"},
        "amount_decimals": 6,
    },
    "hop": {
        "url": "https://api.hop.exchange/quote",
        "chain_ids": {"ethereum": "1", "polygon": "137", "arbitrum": "42161", "optimism": "10"},
        "token_ids": {"USDC": "USDC", "USDT": "USDT"},
        "amount_decimals": 6,
    },
    "across": {
        "url": "https://across.to/api/quote",
        "chain_ids": {"ethereum": "1", "polygon": "137", "arbitrum": "42161", "optimism": "10"},
        "token_ids": {"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7"},
        "amount_decimals": 6,
    },
    "cbridge": {
        "url": "https://cbridge-api.celer.network/quote",
        "chain_ids": {"ethereum": "1", "polygon": "137", "arbitrum": "42161", "optimism": "10"},
        "token_ids": {"USDC": "USDC", "USDT": "USDT"},
        "amount_decimals": 6,
    },
}


@allow_storage
@dataclass
class BridgeQuote:
    quote_id: str
    src_chain: str
    dst_chain: str
    token: str
    amount: str
    best_bridge: str
    best_fee: str
    best_time: str
    best_output: str
    all_quotes: str
    cross_validation: str
    source_agreement: str
    bridges_checked: str
    bridges_retrieved: str
    reasoning: str
    fetched_at: str


class BridgeAggregator(gl.Contract):
    quotes: TreeMap[str, str]
    latest: TreeMap[str, str]
    quote_count: u256

    SUPPORTED_BRIDGES = ("stargate", "hop", "across", "cbridge")
    CROSS_VALIDATION_VALUES = ("PASS", "FAIL", "PARTIAL")

    def __init__(self):
        self.quote_count = 0

    def _decode_body(self, content) -> str:
        body = getattr(content, "body", None)
        if body is None:
            return str(content)
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        return str(body)

    def _validate_result(self, result: dict) -> bool:
        best_bridge = result.get("best_bridge", "")
        if best_bridge not in self.SUPPORTED_BRIDGES and best_bridge != "none":
            return False
        cross_val = result.get("cross_validation", "")
        if cross_val not in self.CROSS_VALIDATION_VALUES:
            return False
        try:
            float(result.get("best_fee", "0"))
            float(result.get("best_time", "0"))
            float(result.get("best_output", "0"))
            int(result.get("source_agreement", "0"))
        except (ValueError, TypeError):
            return False
        return True

    def _build_url(self, bridge: str, src_chain: str, dst_chain: str, token: str, amount: str) -> str:
        adapter = BRIDGE_ADAPTERS.get(bridge)
        if not adapter:
            return ""
        src_id = adapter["chain_ids"].get(src_chain, "")
        dst_id = adapter["chain_ids"].get(dst_chain, "")
        token_id = adapter["token_ids"].get(token, "")
        if not src_id or not dst_id or not token_id:
            return ""
        try:
            amount_int = int(float(amount) * (10 ** adapter["amount_decimals"]))
        except (ValueError, TypeError):
            return ""
        return adapter["url"] + "?srcChainId=" + src_id + "&dstChainId=" + dst_id + "&token=" + token_id + "&amount=" + str(amount_int)

    def _fetch_quote(self, bridge: str, src_chain: str, dst_chain: str, token: str, amount: str) -> dict:
        url = self._build_url(bridge, src_chain, dst_chain, token, amount)
        if not url:
            return {"bridge": bridge, "url": "", "data": "", "retrieved": False}
        try:
            content = gl.nondet.web.render(url)
            body = self._decode_body(content)[:1500]
            if not body:
                return {"bridge": bridge, "url": url, "data": "", "retrieved": False}
            return {"bridge": bridge, "url": url, "data": body, "retrieved": True}
        except Exception:
            return {"bridge": bridge, "url": url, "data": "", "retrieved": False}

    def _find_best_route(self, src_chain: str, dst_chain: str, token: str, amount: str) -> dict:
        def gather_and_compare() -> dict:
            fetched = []
            for bridge in self.SUPPORTED_BRIDGES:
                result = self._fetch_quote(bridge, src_chain, dst_chain, token, amount)
                fetched.append(result)

            retrieved = [f for f in fetched if f.get("retrieved")]
            if not retrieved:
                return {
                    "best_bridge": "none",
                    "best_fee": "0",
                    "best_time": "0",
                    "best_output": "0",
                    "all_quotes": "{}",
                    "cross_validation": "FAIL",
                    "source_agreement": "0",
                    "reasoning": "No bridge data retrieved.",
                }

            parts = []
            for r in retrieved:
                parts.append("[" + r["bridge"] + "] " + r["url"] + ":\n" + r["data"][:300])
            sources_text = "\n".join(parts)

            json_format = chr(123) + chr(34) + "all_quotes" + chr(34) + ": " + chr(123) + chr(34) + "<bridge>" + chr(34) + ": " + chr(123) + chr(34) + "fee" + chr(34) + ": " + chr(34) + "<number>" + chr(34) + ", " + chr(34) + "time" + chr(34) + ": " + chr(34) + "<minutes>" + chr(34) + ", " + chr(34) + "output" + chr(34) + ": " + chr(34) + "<number>" + chr(34) + chr(125) + chr(125) + ", " + chr(34) + "best_bridge" + chr(34) + ": " + chr(34) + "<bridge>" + chr(34) + ", " + chr(34) + "best_fee" + chr(34) + ": " + chr(34) + "<number>" + chr(34) + ", " + chr(34) + "best_time" + chr(34) + ": " + chr(34) + "<minutes>" + chr(34) + ", " + chr(34) + "best_output" + chr(34) + ": " + chr(34) + "<number>" + chr(34) + ", " + chr(34) + "cross_validation" + chr(34) + ": " + chr(34) + "PASS" + chr(34) + "|" + chr(34) + "FAIL" + chr(34) + "|" + chr(34) + "PARTIAL" + chr(34) + ", " + chr(34) + "source_agreement" + chr(34) + ": " + chr(34) + "<0-100>" + chr(34) + ", " + chr(34) + "reasoning" + chr(34) + ": " + chr(34) + "<text>" + chr(34) + chr(125)

            task = (
                "You are a cross-chain bridge aggregator. Compare bridge quotes and find the best route.\n"
                "ROUTE: " + src_chain + " -> " + dst_chain + "\n"
                "TOKEN: " + token + "\n"
                "AMOUNT: " + amount + "\n"
                "BRIDGE QUOTES (" + str(len(retrieved)) + " retrieved):\n" + sources_text + "\n\n"
                "INSTRUCTIONS:\n"
                "1. Extract fee, time (minutes), and output amount from each bridge\n"
                "2. Cross-validate: Compare values between bridges - PASS if consistent, FAIL if they contradict\n"
                "3. source_agreement: percentage of bridges with similar values (0-100)\n"
                "4. Select best_bridge based on lowest fee and reasonable time\n"
                "5. Calculate best_fee, best_time, best_output\n\n"
                "Respond ONLY in JSON: " + json_format
            )
            result = gl.nondet.exec_prompt(task)
            if isinstance(result, str):
                result = json.loads(result.replace("```json", "").replace("```", ""))
            if not isinstance(result, dict):
                raise gl.vm.UserError("[LLM_ERROR] LLM returned non-dict result")
            result["bridges_checked"] = len(self.SUPPORTED_BRIDGES)
            result["bridges_retrieved"] = len(retrieved)
            return result

        principle = (
            "Two results are equivalent if best_bridge matches exactly, "
            "best_fee differs by at most 1%, best_time differs by at most 5 minutes, "
            "best_output differs by at most 1%, "
            "cross_validation matches exactly, "
            "source_agreement differs by at most 10 points, "
            "all_quotes for each bridge fee differs by at most 1%. "
            "reasoning wording may differ."
        )
        return gl.eq_principle.prompt_comparative(gather_and_compare, principle)

    @gl.public.write
    def find_best_route(self, src_chain: str, dst_chain: str, token: str, amount: str) -> str:
        if not src_chain or not src_chain.strip():
            raise gl.vm.UserError("Source chain is required")
        if not dst_chain or not dst_chain.strip():
            raise gl.vm.UserError("Destination chain is required")
        if not token or not token.strip():
            raise gl.vm.UserError("Token is required")
        if not amount or not amount.strip():
            raise gl.vm.UserError("Amount is required")

        result = self._find_best_route(src_chain.strip().lower(), dst_chain.strip().lower(), token.strip().upper(), amount.strip())

        if not self._validate_result(result):
            raise gl.vm.UserError("Invalid consensus result")

        from datetime import datetime, timezone
        self.quote_count += 1
        quote_id = str(self.quote_count)

        quote = BridgeQuote(
            quote_id=quote_id,
            src_chain=src_chain.strip().lower(),
            dst_chain=dst_chain.strip().lower(),
            token=token.strip().upper(),
            amount=amount.strip(),
            best_bridge=str(result.get("best_bridge", "none")),
            best_fee=str(result.get("best_fee", "0")),
            best_time=str(result.get("best_time", "0")),
            best_output=str(result.get("best_output", "0")),
            all_quotes=json.dumps(result.get("all_quotes", {})),
            cross_validation=str(result.get("cross_validation", "FAIL")),
            source_agreement=str(result.get("source_agreement", "0")),
            bridges_checked=str(result.get("bridges_checked", 0)),
            bridges_retrieved=str(result.get("bridges_retrieved", 0)),
            reasoning=str(result.get("reasoning", "")),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        self.quotes[quote_id] = json.dumps(quote.__dict__)
        key = src_chain.strip().lower() + "_" + dst_chain.strip().lower() + "_" + token.strip().upper()
        self.latest[key] = json.dumps(quote.__dict__)
        return quote_id

    @gl.public.view
    def get_quote(self, quote_id: str) -> str:
        return self.quotes.get(str(quote_id), "{}")

    @gl.public.view
    def get_latest(self, src_chain: str, dst_chain: str, token: str) -> str:
        key = src_chain.strip().lower() + "_" + dst_chain.strip().lower() + "_" + token.strip().upper()
        return self.latest.get(key, "{}")

    @gl.public.view
    def get_quote_count(self) -> int:
        return self.quote_count

    @gl.public.view
    def get_supported_bridges(self) -> list:
        return list(self.SUPPORTED_BRIDGES)

    @gl.public.view
    def get_stats(self) -> dict:
        total = 0
        cross_valid = 0
        by_bridge = {}
        for v in self.quotes.values():
            r = json.loads(v)
            total += 1
            bridge = r.get("best_bridge", "none")
            by_bridge[bridge] = by_bridge.get(bridge, 0) + 1
            if r.get("cross_validation") == "PASS":
                cross_valid += 1
        return {
            "total": total,
            "cross_validated": cross_valid,
            "by_bridge": by_bridge,
        }