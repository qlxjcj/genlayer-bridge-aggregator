# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import json
from dataclasses import dataclass
from genlayer import *


BRIDGE_SOURCES = {
    "stargate": "https://api.stargate.finance/quote?srcChain={src}&dstChain={dst}&token={token}&amount={amount}",
    "hop": "https://api.hop.exchange/quote?fromChain={src}&toChain={dst}&token={token}&amount={amount}",
    "across": "https://api.across.to/quote?originChain={src}&destinationChain={dst}&token={token}&amount={amount}",
    "cbridge": "https://cbridge-api.celer.network/quote?src_chain={src}&dst_chain={dst}&token={token}&amount={amount}",
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
    reasoning: str
    fetched_at: str


class BridgeAggregator(gl.Contract):
    quotes: TreeMap[str, str]
    latest: TreeMap[str, str]
    quote_count: u256

    def __init__(self):
        self.quote_count = 0

    def _decode_body(self, content) -> str:
        body = getattr(content, "body", None)
        if body is None:
            return str(content)
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        return str(body)

    def _fetch_quote(self, bridge: str, src_chain: str, dst_chain: str, token: str, amount: str) -> dict:
        url_template = BRIDGE_SOURCES.get(bridge, "")
        if not url_template:
            return {"bridge": bridge, "fee": "0", "time": "0", "output": "0", "retrieved": False}

        url = url_template.format(src=src_chain, dst=dst_chain, token=token, amount=amount)
        try:
            content = gl.nondet.web.render(url)
            body = self._decode_body(content)[:1500]
            return {"bridge": bridge, "url": url, "data": body, "retrieved": True}
        except Exception:
            return {"bridge": bridge, "url": url, "data": "", "retrieved": False}

    def _find_best_route(self, src_chain: str, dst_chain: str, token: str, amount: str) -> dict:
        def gather_and_compare() -> dict:
            fetched = []
            for bridge in BRIDGE_SOURCES:
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
            result["bridges_checked"] = len(BRIDGE_SOURCES)
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
        return list(BRIDGE_SOURCES.keys())

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