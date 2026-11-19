# ihategambling

Autonomous multi-bot web crawler and DNS/hosts blocklist generator for online gambling, betting, and Cambodia-based cyber scam operations (fraud compounds, fake job traps, task scams, and fake investment portals).

Designed for low-resource environments (e.g. ARM single-board computers, TV boxes like Amlogic S905X with 1-2GB RAM) using minimal CPU and memory (< 50MB RAM).

---

## Architecture & Multi-Signal Risk Engine (100-Point Scale)

To prevent false positives on legitimate sites while catching cloaked mirrors and satellite redirectors, the system evaluates all candidates against a 100-point multi-signal heuristic model. A domain is flagged only when **Total Score >= 70**:

1. **Page Content (40 points max)**:
   - Title & Meta Tags (15 pts): Analyzes `<title>`, `<meta name="description">`, and OpenGraph headers for core illegal gambling indicators (`tài xỉu`, `nổ hũ`, `xóc đĩa`, `bắn cá`, `lô đề`, `baccarat`, `kèo nhà cái`, `casino`, `việc làm campuchia`...).
   - Body Keyword Density (15 pts): Evaluates contextual frequency across verified gambling and task-scam vocabularies.
   - Native App Downloads (10 pts): Detects direct `.apk` and `.ipa` download packages or installation landing wrappers.

2. **Redirect & Cloaking Behavior (25 points max)**:
   - HTTP 301/302 Redirect Chains (15 pts): Follows cross-domain hops from cloaked satellite domains to primary betting engines.
   - JavaScript & Meta-Refresh Evasion (10-15 pts): Regex-based parsing of client-side `window.location` and `meta http-equiv="refresh"` destinations. All identified destinations are dynamically enqueued for recursive analysis.

3. **Domain Heuristics (20 points max)**:
   - Brand & Number Patterns (12 pts): Detects illegal gaming brands combined with characteristic lucky numbers or evasion years (e.g. `88`, `77`, `68`, `79`, `388`, `789`, `999`, `2024-2026`).
   - High-Risk Cheap TLDs (8 pts): Correlates with disposable and unverified top-level domains (`.vip`, `.club`, `.win`, `.bet`, `.top`, `.xyz`, `.icu`, `.buzz`, `.cfd`, `.sbs`...).

4. **Infrastructure Signals (15 points max)**:
   - Deposit Support & Chat Widgets (7 pts): Uncovers embedded Telegram bots, LiveChat, Tawk.to, and Zalo chat gateways.
   - Reverse-Proxy Headers (4 pts): Identifies Cloudflare fronting and edge caching layers.
   - SSL Certificate Attributes (4 pts): Direct SSL socket analysis inspecting short-lived or free certificate authorities (Let's Encrypt, ZeroSSL, recent issuances < 60 days).

---

## Ingestion Pipelines

- **Synthetic Domain Generator & DNS Prober**: Programmatically generates brand-number-TLD permutations and verifies active resolutions via asynchronous low-latency DNS lookups before crawling.
- **Certificate Transparency Logs (`crt.sh`)**: Queries real-time SSL transparency databases to uncover newly registered domain mirrors as soon as certificates are requested.
- **Anti-Cloaking Mobile User-Agent Engine**: Simulates authentic Vietnamese mobile devices (iOS Safari, Android Chrome) with `vi-VN` locale headers to bypass geo-blocking and desktop cloaking filters.
- **Search Engine Discovery**: Queries public search indexes for active gambling and cross-border cyber compound campaigns.
- **Strict Whitelist**: Immune to false alarms on major portals (Google, YouTube, Facebook, Vietnamese news outlets).

---

## Project Structure

- `gambling-crawler.py`: Multithreaded continuous crawler featuring the 100-point scoring engine, synthetic generator, crt.sh harvester, and mobile anti-cloaking.
- `gambling-blocker.py`: Community blacklist aggregator (pulls over 600,000 verified domains from HaGeZi, StevenBlack, and hostsVN) with `/etc/hosts` synchronization.
- `keywords.json`: Dynamic vocabulary defining brand prefixes, suffixes, high-risk TLDs, and scam indicators.
- `suspicious_domains.txt`: Output list of verified suspicious domains formatted for DNS sinkholing.
- `requirements.txt`: Lightweight Python dependencies (`requests`, `beautifulsoup4`).

---

## Installation

```bash
git clone https://github.com/starfish367/ihategambling.git
cd ihategambling
pip3 install -r requirements.txt
```

---

## Usage

### 1. Continuous Multi-Bot Crawler (`gambling-crawler.py`)

Run 16 concurrent bots:
```bash
python3 gambling-crawler.py --threads 16 --output suspicious_domains.txt
```

Run in timed batch mode (e.g., 15 minutes):
```bash
python3 gambling-crawler.py --threads 16 --minutes 15 --output suspicious_domains.txt
```

### 2. Blacklist Aggregator & System Blocker (`gambling-blocker.py`)

Fetch and consolidate external blacklists:
```bash
python3 gambling-blocker.py
```

Inspect a specific suspicious URL:
```bash
python3 gambling-blocker.py --scan https://example-gambling-site.com
```

Apply the blocklist directly to `/etc/hosts`:
```bash
sudo python3 gambling-blocker.py --apply
```

---

## Output Format

Domains verified by the multi-signal engine are appended in standard hosts format:
```
0.0.0.0 kubetvip.lol # 2026-11-19 23:12:37 | Diem: 86/100 (ND:40, CH:15, TM:20, HT:11) | Ly do: Pattern thuong hieu/so co bac, TLD rui ro cao, HTTP Redirect sang m.meslot202.com, Title/Meta: bắn cá, Body kw (13), Tải bản cài APK/IPA, Widget CSKH/Telegram, Cloudflare Proxy
```

---

## License

MIT License.
