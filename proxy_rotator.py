"""
Auto-rotating free Indian proxy pool with instant failover.
Maintains a pool of working proxies and switches immediately on failure.
"""
import requests
import random
import time
import os
import json
import threading

_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".proxy_cache.json")
_POOL_SIZE   = 5          # Keep 5 working proxies ready
_CACHE_TTL   = 600        # Refresh pool every 10 minutes
_TEST_TIMEOUT = 10        # Seconds per proxy test

_lock = threading.Lock()

PROXY_SOURCES = [
    # ProxyScrape — Indian HTTP
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=IN&ssl=all&anonymity=all",
    # ProxyScrape — global HTTP (fallback)
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=4000&country=all&ssl=all&anonymity=elite",
    # ProxyScrape — SOCKS5 India
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=IN",
    # TheSpeedX big list
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    # clarketm list
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    # monosans/proxy-list
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    # roosterkid list
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    # mmpx12
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    # GeoNode free API
    "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&country=IN&protocols=http",
]

TEST_URL     = "https://tathya.uidai.gov.in/audioCaptchaService/api/captcha/v3/generation"
TEST_HEADERS = {
    "Content-Type": "application/json",
    "appID":        "MYAADHAAR",
    "Origin":       "https://myaadhaar.uidai.gov.in",
}
TEST_BODY = '{"captchaLength":"6","captchaType":"2","audioCaptchaRequired":true}'


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cache(data: dict):
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# ── Fetch proxy list from all sources ─────────────────────────────────────────

def _fetch_all_proxies() -> list:
    proxies = []
    for url in PROXY_SOURCES:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code != 200:
                continue
            # GeoNode returns JSON
            if "geonode" in url:
                try:
                    items = r.json().get("data", [])
                    for item in items:
                        host = item.get("ip", "")
                        port = item.get("port", "")
                        if host and port:
                            proxies.append(f"{host}:{port}")
                except Exception:
                    pass
            else:
                for line in r.text.strip().splitlines():
                    line = line.strip()
                    if line and ":" in line and not line.startswith("#"):
                        proxies.append(line)
        except Exception:
            continue
    # Deduplicate + shuffle
    proxies = list(set(proxies))
    random.shuffle(proxies)
    return proxies


# ── Test a single proxy against UIDAI ─────────────────────────────────────────

def _test_proxy(proxy_str: str) -> str | None:
    if proxy_str.startswith("http"):
        proxy_url = proxy_str
    else:
        proxy_url = f"http://{proxy_str}"
    try:
        r = requests.post(
            TEST_URL,
            headers=TEST_HEADERS,
            data=TEST_BODY,
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=_TEST_TIMEOUT,
        )
        if r.status_code in (200, 400, 403, 422, 429):
            return proxy_url
    except Exception:
        pass
    return None


# ── Build a pool of working proxies ───────────────────────────────────────────

def _build_pool(verbose=False) -> list:
    if verbose:
        print("🔍 [PROXY] Fetching proxy list from multiple sources...")
    all_proxies = _fetch_all_proxies()
    if verbose:
        print(f"🔍 [PROXY] Got {len(all_proxies)} candidates — testing up to 80 against UIDAI...")

    pool = []
    tested = 0
    for proxy_str in all_proxies:
        if len(pool) >= _POOL_SIZE:
            break
        tested += 1
        if tested > 80:
            break
        result = _test_proxy(proxy_str)
        if result:
            pool.append(result)
            host = result.split("@")[-1] if "@" in result else result
            if verbose:
                print(f"  ✅ Working proxy found: {host} ({len(pool)}/{_POOL_SIZE})")

    if verbose:
        print(f"🔍 [PROXY] Pool built: {len(pool)} working proxies")
    return pool


# ── Public API ─────────────────────────────────────────────────────────────────

def get_working_proxy(verbose=False) -> str | None:
    """Return a proxy from the pool. Auto-rebuilds pool if stale/empty."""
    with _lock:
        cache = _load_cache()
        pool  = cache.get("pool", [])
        ts    = cache.get("ts", 0)

        # Pool is fresh and has entries — return first one
        if pool and (time.time() - ts) < _CACHE_TTL:
            proxy = pool[0]
            if verbose:
                host = proxy.split("@")[-1] if "@" in proxy else proxy
                print(f"🔀 [PROXY] Using cached proxy: {host} ({len(pool)} in pool)")
            return proxy

        # Rebuild pool
        if verbose:
            print("⚠️ [PROXY] Pool empty or stale — rebuilding...")
        new_pool = _build_pool(verbose=verbose)
        if new_pool:
            _save_cache({"pool": new_pool, "ts": time.time()})
            if verbose:
                print(f"✅ [PROXY] Pool ready with {len(new_pool)} proxies")
            return new_pool[0]

        if verbose:
            print("❌ [PROXY] No working proxy found — trying direct connection")
        return None


def invalidate_proxy(bad_proxy: str, verbose=False):
    """Mark a proxy as dead — immediately removes it from pool so next call gets a fresh one."""
    with _lock:
        cache = _load_cache()
        pool  = cache.get("pool", [])
        before = len(pool)
        pool = [p for p in pool if p != bad_proxy]
        if verbose and len(pool) < before:
            host = bad_proxy.split("@")[-1] if "@" in bad_proxy else bad_proxy
            print(f"🔄 [PROXY] Removed dead proxy: {host} — {len(pool)} remaining in pool")
        # Save immediately; if pool is now empty, next get_working_proxy will rebuild
        _save_cache({"pool": pool, "ts": cache.get("ts", 0)})


def refresh_pool_background(verbose=False):
    """Spawn a background thread to pre-warm the pool (non-blocking)."""
    def _worker():
        with _lock:
            new_pool = _build_pool(verbose=verbose)
            if new_pool:
                _save_cache({"pool": new_pool, "ts": time.time()})
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
