# AGENTS.md — JustOne

> 子域名收集工具 (subdomain collection tool). Python 3.14. CLIs via Typer + Rich.

## Setup

```bash
# Windows venv
venv\Scripts\activate

# Install
pip install -r requirements.txt        # runtime deps
pip install -e ".[dev]"                # or editable install incl. pytest/ruff
# Optional engine clients (shodan, leakix) are in requirements.txt / pyproject extras.
```

Project metadata, pytest and ruff config live in `pyproject.toml`.

## Running

```bash
python justone.py main example.com                # full collect (search + certs + datasets + brute)
python justone.py main example.com --no-brute     # skip brute
python justone.py main example.com -v             # verbose (debug logging)
python justone.py check example.com               # HTTP liveness check
python justone.py check example.com --dns          # DNS-only check
python justone.py check -i subdomains.txt          # batch from file
python justone.py brute example.com               # brute-force only
```

## Testing

```bash
pytest                          # full suite incl. network tests (slow, hits real APIs)
pytest -m "not network" -q      # unit layer only — fast, no network, what CI runs
pytest -m network -q            # network layer only
pytest tests/test_search_baidu.py              # single module test
pytest -k "test_collect"                        # filter by keyword
```

Tests use `config/.env` for real API keys. Modules missing keys are skipped via `have_api()` guard — **7 skips is normal**.

Tests use **unittest** (not pytest-native). `pytest` works as a unittest runner; config in `pyproject.toml`. Network-dependent files (search baidu/bing, crtsh, socks5 traffic, justone e2e, collect) carry `pytestmark = pytest.mark.network`. GitHub Actions runs the unit layer only (`.github/workflows/tests.yml`).

## ⚠️ Encoding

| Area | Encoding |
|------|----------|
| Source files (`*.py`) | Unix line endings, UTF-8 (no BOM). `# -*- coding: utf-8 -*-` header on some files. |
| `DevLog/*.md` | UTF-8 |
| `modules/search/yahoo.py` | **UTF-8-SIG** (UTF-8 with BOM) — sole outlier. Strip BOM if editing. |
| All other files | UTF-8 |

> 历史遗留：2026-05-13 至 2026-06-10 期间的 DevLog 文件为 GBK 编码（VSCode 中会乱码）。新日志统一使用 UTF-8。

## Architecture

```
justone.py          ← Typer CLI entry (main/check/brute commands)
config/
  settings.py       ← Pydantic BaseSettings. Reads config/.env. Fields auto-load from env vars.
  .env              ← API keys (gitignored). Copy from .env.example.
  logging.py        ← loguru init (file + stderr)
common/
  module.py         ← Module base class (requests-based)
  domain.py         ← Domain parsing / registered domain extraction
  utils.py          ← match_subdomains(), dns_query(), gen_fake_header()
  resolve.py        ← DNS batch resolution
  database.py       ← SQLite persistence
modules/
  collect.py        ← Collect scheduler. Async (asyncio) scheduling with Semaphore concurrency + per-module timeout.
  search/           ← 13 search engines (baidu, bing, google, yahoo, fofa, hunter, shodan, zoomeye, so, sogou, yandex, gitee, github)
  certificates/     ← crtsh, certspotter, censys
  datasets/         ← 17 modules (anubis, chinaz, circl, cloudflare, dnsdb, dnsdumpster, fullhunt, hackertarget, ip138, leakix, netcraft, passivedns, rapiddns, robtex, securitytrails, sitedossier)
  check/            ← http, dns, cdn, axfr, cert, csp, nsec, robots, sitemap, crossdomain
  dnsquery/         ← mx, ns, soa, spf, txt
  intelligence/     ← otx, urlscan, threatbook, virustotal, threatminer
  brute.py          ← DNS brute-force
  altdns.py         ← subdomain permutation
  enrich.py         ← enrich records in SQLite
  takeover.py       ← subdomain takeover detection
  export.py         ← CSV/JSON/TXT output
data/               ← wordlists, CDN fingerprints, public_suffix_list.dat
```

## Module Pattern

Every module follows this contract:

```python
from common.module import Module

class Foo(Module):
    def __init__(self, domain: str, config: dict = None):
        super().__init__(domain, config)
        self.module = 'Foo'          # display name
        self.source = 'foo.com'      # data source identifier

    def run(self) -> set:
        if not self.have_api(self.api_key):   # skip if no key
            return set()
        # ... fetch data ...
        return self.collect_subdomains(resp)  # uses match_subdomains internally
```

**Registration (2 places to touch)**:
1. `modules/<type>/__init__.py` — import and export the class + `run` function
2. `modules/collect.py` — add the class name to the matching entry in `Collect._MODULE_SPECS` (registry-driven loader)
3. `.env` / `settings.py` — if new API key required

## ⚠️ Proxy Behavior: Proxy-First, Direct-Fallback

`common/module.py:_do_request()` **tries proxy first when configured** (attempt 0: `proxies=self.proxy`), then falls back to direct (attempt 1: `proxies=None`). This means:

- When `PROXY_ENABLE=true` + `PROXY_POOL=...`: request goes through proxy first, direct fallback on failure
- When `PROXY_ENABLE=false`: both attempts use direct connection (no proxy overhead)
- `self.proxy` is initialized at module construction via `utils.get_random_proxy()` if `proxy_enable=True`
- `common/async_module.py` follows the same proxy-first pattern for both `async_get` / `async_post`
- **For foreign-only accessible targets, Playwright-based modules** (Google, Yahoo) set proxy at browser-context level, independent of this HTTP-level proxy

## Adding a New Module

1. Create `modules/<type>/<name>.py` following the Module pattern above
2. Register in `modules/<type>/__init__.py`:
   ```python
   from .<name> import <ClassName>, run as <name>_run
   ```
3. Add the class name to the matching entry in `Collect._MODULE_SPECS` (`modules/collect.py`)
4. If it needs an API key: add field to `config/.env.example` and `config/settings.py`

## Config Priority

1. CLI args (`--no-search`, `--no-brute`, `-v`)
2. Environment variables → `config/.env` → `config/settings.py` (pydantic-settings)
3. `common/module.py` `http_config` dict (per-module overrides)
4. `modules/collect.py` `collect_config` dict (scheduler defaults)

## Scripts & Commands

| What | Command |
|------|---------|
| Full test suite | `pytest` |
| Single test file | `pytest tests/test_search_baidu.py` |
| Specific test | `pytest -k "test_baidu"` |
| Run with timeout debug | `python justone.py main example.com -v 2>&1 \| tee run.log` |

## Code Style

- Chinese docstrings on all public methods/classes (see `.skills/code-style-unifier/`)
- Type hints where practical: `Set[str]`, `Optional[dict]`, `List[Dict[str, Any]]`
- Module classes inherit from `common.module.Module`
- Sphinx-style docstrings: `:param`, `:return`, `:raises`

## Known Issues & Watch Points

| Issue | Detail |
|-------|--------|
| **censys.io requests failing** | Unresolved as of 2026-05-23. Likely API auth or endpoint issue. |
| **Cloudflare API returning 0 results** | Unresolved as of 2026-05-23. May be zone/account mismatch. |
| **7 skipped tests normal** | API-key-dependent modules skip when unconfigured. |
| **`robtex.py:48` assignment-overwrite pattern** | Historical bug (fixed). `self.collect_subdomains(resp)` not `self.subdomains =`. |
