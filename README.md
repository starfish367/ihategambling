# ihategambling

Autonomous multi-bot web crawler and DNS/hosts blocklist generator for online gambling, betting, and Cambodia-based cyber scam operations (fraud compounds, fake job traps, task scams, and fake investment portals).

Designed for low-resource environments (e.g. ARM single-board computers, TV boxes like Amlogic S905X with 1-2GB RAM) using minimal CPU and memory (< 50MB RAM).

---

## Features

- **Search Engine Scraping**: Discovers emerging gambling portals, mirror networks, and Cambodia fake job / task scam traps directly from search engine queries without requiring paid APIs or encountering CAPTCHAs.
- **Domain Heuristics**: Automatically detects gambling and fraud naming patterns (common English prefixes combined with numbers such as `88`, `77`, `68`, `79`, `388`, `789`, `999`...).
- **Anti-Cambodia Scam Intelligence**: Scans for patterns related to cross-border scam operations (Bavet, Chrey Thum, Sihanoukville, "việc nhẹ lương cao", fake job telesale traps, and Shopee/TikTok order-grabbing task scams).
- **Deep Link Harvesting**: Crawls incoming landing pages and extracts outgoing affiliate / backup mirror links to uncover entire networks of related betting and scam sites.
- **Content Scoring**: Inspects HTML structure, titles, and body keywords (`cá cược`, `kèo nhà cái`, `tài xỉu`, `baccarat`, `đá gà`, `casino`, `việc làm campuchia`, `nhiệm vụ nhận hoa hồng`...) to verify malicious intent.
- **Free Proxy Rotation**: Built-in dynamic fetcher and rotator pulling thousands of public HTTP proxies with automatic fallback.
- **Multi-Bot Concurrency**: Configurable multithreaded workers (`--threads N`).
- **Automated Cloud Workflows**: Continuous execution and automatic domain updates via scheduled GitHub Actions.
- **System-level Protection**: Exports standard `0.0.0.0 domain` format compatible with `/etc/hosts`, AdGuard Home, Pi-hole, and DNSmasq.

---

## Project Structure

- `gambling-crawler.py`: Continuous multi-bot crawler with proxy rotation, dynamic queries, and recursive link harvesting.
- `gambling-blocker.py`: Community blacklist aggregator (pulls over 600k verified domains from HaGeZi, StevenBlack) with an automatic `/etc/hosts` applier.
- `suspicious_domains.txt`: Output list of newly identified gambling domains.
- `requirements.txt`: Python package requirements (`requests`, `beautifulsoup4`).

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

Run 12 concurrent bots with automatic proxy rotation:
```bash
python3 gambling-crawler.py --threads 12 --output suspicious_domains.txt
```

Run with custom keywords:
```bash
python3 gambling-crawler.py --query "tài xỉu online" --threads 8
```

Run without proxies (direct mode):
```bash
python3 gambling-crawler.py --no-proxy --threads 4
```

### 2. Blacklist Aggregator & System Blocker (`gambling-blocker.py`)

Fetch hundreds of thousands of established gambling domains from community feeds:
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

## License

MIT License. See [LICENSE](LICENSE) for details.
