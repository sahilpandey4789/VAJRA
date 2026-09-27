"""
Chain adapter layer - Technical Defense Document, section 5.

The core engine (clustering + scoring) operates on a normalised
transaction schema and never talks to a chain API directly. Adding a
new chain means writing one adapter, not touching the engine.

Every chain now has:
  - a Mock adapter, returning the offline fixture graphs (used whenever
    VAJRA_LIVE_MODE is off, or as the automatic fallback if every live
    provider for that chain fails)
  - one or more real Live adapters, each hitting a genuine free/free-tier
    block-explorer API over HTTPS with retry + exponential backoff, a
    hard timeout, and structured logging. A ChainFailoverAdapter tries
    them in order and only gives up (raising, so the caller can fall
    back to Mock) once every configured provider has failed.

Note: these live adapters have not yet been exercised against real
provider traffic - the endpoint shapes, params and response parsing
below are written directly against each provider's published API docs.
Set VAJRA_LIVE_MODE=1 with real keys in .env to use them for real. See
docs/ARCHITECTURE.md "API dependency & resilience".

Normalised transaction shape (chain-independent):
    {
        "tx_hash": str,
        "inputs": [address, ...],          # co-spend signal lives here
        "outputs": [{"address": str, "value": float}, ...],
        "fee": float,
        "timestamp": ISO-8601 str,
        "hop": int,
    }
"""
import logging
import os
import time

from engine import fixtures
from engine import cache as vajra_cache

try:
    import requests
except ImportError:  # pragma: no cover - requests ships in this build's requirements.txt
    requests = None

log = logging.getLogger("vajra.chain_adapters")

REQUEST_TIMEOUT_SECONDS = float(os.environ.get("VAJRA_API_TIMEOUT", "8"))
MAX_RETRIES = int(os.environ.get("VAJRA_API_MAX_RETRIES", "3"))
BACKOFF_BASE_SECONDS = 0.6
LIVE_CACHE_TTL_SECONDS = int(os.environ.get("VAJRA_LIVE_CACHE_TTL", "120"))


class ChainAdapter:
    chain_name = "abstract"
    provider_name = "mock"

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        raise NotImplementedError


class AdapterError(Exception):
    """Raised by a live adapter when it cannot serve a real answer."""


class MockAdapter(ChainAdapter):
    """Serves the offline fixture graph for a seeded demo wallet."""

    provider_name = "offline-fixture"

    def __init__(self, chain_name, fixture_key):
        self.chain_name = chain_name
        self.fixture_key = fixture_key

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        fx = fixtures.FIXTURE_MAP.get(self.fixture_key)
        if not fx:
            return []
        return [t for t in fx["transactions"] if t["hop"] <= max_hops]


def _get_with_retry(url, params=None, headers=None, provider="unknown"):
    """
    Shared HTTP-GET helper: hard timeout, exponential backoff on 429/5xx
    and connection errors, capped at MAX_RETRIES. Never retries on a
    clean 4xx (bad address, bad key) - that fails fast.
    """
    if requests is None:
        raise AdapterError("the 'requests' package is not installed")
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        started = time.monotonic()
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise AdapterError(f"{provider} returned HTTP {resp.status_code}")
            resp.raise_for_status()
            log.info("live_api_call provider=%s status=%s elapsed_ms=%s", provider, resp.status_code, elapsed_ms)
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - deliberately broad, retried uniformly
            last_exc = exc
            log.warning("live_api_call_failed provider=%s attempt=%s/%s error=%s",
                        provider, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    raise AdapterError(f"{provider} failed after {MAX_RETRIES} attempts: {last_exc}")


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts)))


# ---------------------------------------------------------------- Ethereum --
class LiveEtherscanAdapter(ChainAdapter):
    """
    GET https://api.etherscan.io/api?module=account&action=txlist
        &address={address}&sort=asc&apikey={ETHERSCAN_API_KEY}
    Free tier: 5 req/sec, no cost. https://docs.etherscan.io
    """
    chain_name = "ETHEREUM"
    provider_name = "etherscan"

    def __init__(self):
        self.api_key = os.environ.get("ETHERSCAN_API_KEY")

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        if not self.api_key:
            raise AdapterError("ETHERSCAN_API_KEY not set")
        data = _get_with_retry(
            "https://api.etherscan.io/api",
            params={"module": "account", "action": "txlist", "address": address,
                    "sort": "asc", "apikey": self.api_key},
            provider=self.provider_name,
        )
        if data.get("status") != "1" and data.get("message") != "No transactions found":
            raise AdapterError(f"etherscan error: {data.get('message')}")
        out = []
        for i, tx in enumerate(data.get("result", [])[:200]):
            out.append({
                "tx_hash": tx["hash"],
                "inputs": [tx["from"]],
                "outputs": [{"address": tx["to"], "value": int(tx.get("value", 0)) / 1e18}],
                "fee": (int(tx.get("gasUsed", 0)) * int(tx.get("gasPrice", 0))) / 1e18,
                "timestamp": _iso(tx["timeStamp"]),
                "hop": min(i // 3 + 1, max_hops),
            })
        return out


class LiveBlockscoutAdapter(ChainAdapter):
    """
    Backup Ethereum provider (no key required, generous free rate limit).
    GET https://eth.blockscout.com/api/v2/addresses/{address}/transactions
    """
    chain_name = "ETHEREUM"
    provider_name = "blockscout"

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        data = _get_with_retry(
            f"https://eth.blockscout.com/api/v2/addresses/{address}/transactions",
            provider=self.provider_name,
        )
        items = data.get("items", [])
        out = []
        for i, tx in enumerate(items[:200]):
            to_addr = (tx.get("to") or {}).get("hash") or address
            out.append({
                "tx_hash": tx["hash"],
                "inputs": [(tx.get("from") or {}).get("hash")],
                "outputs": [{"address": to_addr, "value": int(tx.get("value", 0)) / 1e18}],
                "fee": float(tx.get("fee", {}).get("value", 0) or 0) / 1e18,
                "timestamp": tx.get("timestamp", _iso(time.time())),
                "hop": min(i // 3 + 1, max_hops),
            })
        return out


# ----------------------------------------------------------------- Bitcoin --
class LiveBlockstreamAdapter(ChainAdapter):
    """
    GET https://blockstream.info/api/address/{address}/txs
    No key required. https://github.com/Blockstream/esplora/blob/master/API.md
    """
    chain_name = "BITCOIN"
    provider_name = "blockstream"

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        data = _get_with_retry(
            f"https://blockstream.info/api/address/{address}/txs",
            provider=self.provider_name,
        )
        out = []
        for i, tx in enumerate(data[:200]):
            inputs = [vin.get("prevout", {}).get("scriptpubkey_address") for vin in tx.get("vin", [])]
            outputs = [{"address": vout.get("scriptpubkey_address"), "value": vout.get("value", 0) / 1e8}
                       for vout in tx.get("vout", [])]
            ts = tx.get("status", {}).get("block_time") or time.time()
            out.append({
                "tx_hash": tx["txid"],
                "inputs": [a for a in inputs if a],
                "outputs": [o for o in outputs if o["address"]],
                "fee": tx.get("fee", 0) / 1e8,
                "timestamp": _iso(ts),
                "hop": min(i // 3 + 1, max_hops),
            })
        return out


class LiveMempoolSpaceAdapter(ChainAdapter):
    """Backup Bitcoin provider - mempool.space mirrors the Esplora API."""
    chain_name = "BITCOIN"
    provider_name = "mempool.space"

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        data = _get_with_retry(
            f"https://mempool.space/api/address/{address}/txs",
            provider=self.provider_name,
        )
        out = []
        for i, tx in enumerate(data[:200]):
            inputs = [vin.get("prevout", {}).get("scriptpubkey_address") for vin in tx.get("vin", [])]
            outputs = [{"address": vout.get("scriptpubkey_address"), "value": vout.get("value", 0) / 1e8}
                       for vout in tx.get("vout", [])]
            ts = tx.get("status", {}).get("block_time") or time.time()
            out.append({
                "tx_hash": tx["txid"],
                "inputs": [a for a in inputs if a],
                "outputs": [o for o in outputs if o["address"]],
                "fee": tx.get("fee", 0) / 1e8,
                "timestamp": _iso(ts),
                "hop": min(i // 3 + 1, max_hops),
            })
        return out


# -------------------------------------------------------------------- Tron --
class LiveTronGridAdapter(ChainAdapter):
    """
    GET https://api.trongrid.io/v1/accounts/{address}/transactions
        header TRON-PRO-API-KEY: {TRONGRID_API_KEY}
    Free tier key: https://www.trongrid.io
    """
    chain_name = "TRON"
    provider_name = "trongrid"

    def __init__(self):
        self.api_key = os.environ.get("TRONGRID_API_KEY")

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        headers = {"TRON-PRO-API-KEY": self.api_key} if self.api_key else {}
        data = _get_with_retry(
            f"https://api.trongrid.io/v1/accounts/{address}/transactions",
            params={"limit": 200}, headers=headers, provider=self.provider_name,
        )
        out = []
        for i, tx in enumerate(data.get("data", [])):
            contract = (tx.get("raw_data", {}).get("contract") or [{}])[0]
            value_info = contract.get("parameter", {}).get("value", {})
            to_addr = value_info.get("to_address", address)
            from_addr = value_info.get("owner_address", address)
            amount = value_info.get("amount", 0) / 1e6
            out.append({
                "tx_hash": tx.get("txID"),
                "inputs": [from_addr],
                "outputs": [{"address": to_addr, "value": amount}],
                "fee": tx.get("ret", [{}])[0].get("fee", 0) / 1e6 if tx.get("ret") else 0,
                "timestamp": _iso(tx.get("block_timestamp", time.time() * 1000) / 1000),
                "hop": min(i // 3 + 1, max_hops),
            })
        return out


class LiveTronScanAdapter(ChainAdapter):
    """Backup Tron provider - public TronScan API, no key required."""
    chain_name = "TRON"
    provider_name = "tronscan"

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        data = _get_with_retry(
            "https://apilist.tronscanapi.com/api/transaction",
            params={"address": address, "limit": 200, "sort": "-timestamp"},
            provider=self.provider_name,
        )
        out = []
        for i, tx in enumerate(data.get("data", [])):
            out.append({
                "tx_hash": tx.get("hash"),
                "inputs": [tx.get("ownerAddress", address)],
                "outputs": [{"address": tx.get("toAddress", address), "value": float(tx.get("amount", 0)) / 1e6}],
                "fee": float(tx.get("cost", {}).get("fee", 0) or 0) / 1e6,
                "timestamp": _iso(tx.get("timestamp", time.time() * 1000) / 1000),
                "hop": min(i // 3 + 1, max_hops),
            })
        return out


# -------------------------------------------------------------- failover --
class ChainFailoverAdapter(ChainAdapter):
    """
    Wraps an ordered list of live adapters for one chain, plus a
    response cache (engine.cache - Redis if configured, in-memory TTL
    otherwise). Tries each provider in turn; on failure logs and moves
    to the next; if all fail, raises AdapterError so the caller
    (engine.tracer) can fall back to the offline Mock adapter - the UI
    shows this to the investigator as a clear "Live API unavailable - showing cached demo data" message, never a crash or a silent hang.
    """

    def __init__(self, chain_name, providers):
        self.chain_name = chain_name
        self.providers = providers
        self.last_provider_used = None
        self.last_error = None

    def fetch_forward_transactions(self, address: str, max_hops: int = 6):
        cache_key = f"chaindata:{self.chain_name}:{address}:{max_hops}"
        cached = vajra_cache.get(cache_key)
        if cached is not None:
            self.last_provider_used = "cache"
            return cached

        for provider in self.providers:
            try:
                result = provider.fetch_forward_transactions(address, max_hops=max_hops)
                self.last_provider_used = provider.provider_name
                vajra_cache.set(cache_key, result, ttl_seconds=LIVE_CACHE_TTL_SECONDS)
                return result
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                log.warning("provider_failed chain=%s provider=%s error=%s - trying next",
                            self.chain_name, provider.provider_name, exc)
                continue
        raise AdapterError(
            f"all live providers exhausted for {self.chain_name}: {self.last_error}"
        )


LIVE_PROVIDER_CHAINS = {
    "ETHEREUM": [LiveEtherscanAdapter, LiveBlockscoutAdapter],
    "BITCOIN": [LiveBlockstreamAdapter, LiveMempoolSpaceAdapter],
    "TRON": [LiveTronGridAdapter, LiveTronScanAdapter],
}


def get_adapter(chain: str, fixture_key: str = None) -> ChainAdapter:
    """
    Adapter factory. VAJRA_LIVE_MODE=1 routes to a ChainFailoverAdapter
    trying every configured live provider for that chain in order;
    anything else (including the default, or every live provider
    failing) routes to the offline mock adapter, which is what keeps
    the demo zero-internet per the offline-first strategy.
    """
    live = os.environ.get("VAJRA_LIVE_MODE") == "1"
    chain = chain.upper()
    if live and chain in LIVE_PROVIDER_CHAINS:
        providers = [cls() for cls in LIVE_PROVIDER_CHAINS[chain]]
        return ChainFailoverAdapter(chain, providers)
    return MockAdapter(chain, fixture_key)


def provider_health_snapshot():
    """
    Best-effort status of each configured live provider, for the
    system-status widget (GET /api/system/status). This only inspects
    configuration (live-mode flag + whether a key is present) rather
    than firing a live probe request per provider on every dashboard
    load - cheap, and honest about what it's actually checking.
    """
    live = os.environ.get("VAJRA_LIVE_MODE") == "1"
    out = []
    for chain, classes in LIVE_PROVIDER_CHAINS.items():
        for cls in classes:
            inst = cls()
            key_required = hasattr(inst, "api_key")
            key_present = bool(getattr(inst, "api_key", "always")) if key_required else True
            out.append({
                "chain": chain,
                "provider": inst.provider_name,
                "requires_key": key_required,
                "status": "ready" if (live and key_present) else ("disabled" if not live else "missing_key"),
            })
    return out
