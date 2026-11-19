# ihategambling

Autonomous multi-bot web crawler and DNS/hosts blocklist generator for online gambling, betting, and Cambodia-based cyber scam operations (fraud compounds, fake job traps, task scams, and fake investment portals).

Designed for low-resource environments (e.g. ARM single-board computers, TV boxes like Amlogic S905X with 1-2GB RAM) using minimal CPU and memory (< 50MB RAM).

---

## 1. Multi-Signal Scoring Engine (100-Point Scale)

Each candidate domain is inspected against four signal groups with an automatic penalty-based false positive mitigation engine:

| Signal Group | Specific Indicator | Detection Mechanism | Points |
| :--- | :--- | :--- | :--- |
| **Content & UI (40 pts)** | High-density gambling keywords | >= 5 occurrences in `<title>`, `<meta>`, `<h1>`-`<h3>` (`tài xỉu`, `nổ hũ`, `xóc đĩa`, `lô đề`...) | **+15** |
| | Real-money transaction phrases | Regex matching on `<button>`, banner, CTA (`nạp rút 1:1`, `momo`, `giftcode tân thủ`, `thưởng nạp`...) | **+15** |
| | Sideloaded app download links | Direct links to `.apk`, `.ipa`, or iOS configuration profile (`.mobileconfig`) | **+10** |
| **Redirect & Cloaking (25 pts)** | Automatic redirect | HTTP 301/302 or JavaScript destination redirecting across domains upon page load | **+15** |
| | Cloaking evasion | Content disparity (>50% size diff or 403/404) between Mobile VN headers vs Desktop | **+10** |
| **Domain Heuristics (20 pts)** | Brand or characteristic pattern | Regex match on gaming brands (`kubet`, `sunwin`, `go88`, `789`, `hi88`, `jun88`, `tx`, `nohu`, `bet`...) | **+12** |
| | High-risk cheap TLD | Uses high-risk extensions (`.vip`, `.club`, `.win`, `.bet`, `.top`, `.xyz`, `.icu`, `.buzz`, `.cfd`...) | **+8** |
| **Infrastructure (15 pts)** | Free SSL newly issued | Let's Encrypt or ZeroSSL certificate issued under 30 days ago | **+8** |
| | Direct deposit/support channel | Embedded LiveChat widget or direct destination to `t.me/` (Telegram) | **+7** |

---

## 2. False Positive Mitigation (Pre-Filter & Penalty Rules)

To eliminate false alarms on legitimate news, casual games, and registered businesses:

- **Pre-Filter Whitelist**:
  - Automatically skips all `.gov.vn`, `.edu.vn`, and `.gov` authorities.
  - Automatically skips pages embedding official Ministry of Industry & Trade verification badges (`online.gov.vn`).
  - Strict whitelist covering major Vietnamese news portals (`vnexpress.net`, `tuoitre.vn`, `thanhnien.vn`, `vtv.vn`...).

- **News & Warning Article Penalty (-35 points)**:
  - Investigative journalism reporting on dismantled gambling rings contains numerous gambling terms.
  - If text content exceeds **800 words** inside `<article>`/body with **NO registration/login form** and **NO deposit button**, the engine applies a **-35 point penalty**.

- **Official App Store Penalty (-30 points)**:
  - Casual games (free card/fish games) use similar terminology without real-money cashouts.
  - If download anchors link directly to `play.google.com` or `apps.apple.com` (and not external `.apk`/`.ipa`), a **-30 point penalty** is applied.

- **Legitimate Business Verification Penalty (-25 points)**:
  - Legitimate businesses (e.g. sports clubs, furniture shops) sharing brand roots.
  - If the footer contains a verified Vietnamese Tax Code (`Mã số thuế` / MST: 10 or 13 digits), an authentic Vietnamese address, and no hidden redirects, a **-25 point penalty** is applied.

---

## 3. Classification Scale

- **70 – 100 points**: **VI PHAM (Confirmed Illegal Gambling)**
  - Automatically appended to `suspicious_domains.txt` formatted for `/etc/hosts` and DNS sinkholes.
- **40 – 69 points**: **NGHI NGO (Suspicious Zone)**
  - Appended to `suspect_review.txt` for secondary verification.
- **Below 40 points**: **AN TOAN (Safe)**
  - Filtered out; insufficient signals to warrant blocking.

---

## 4. Ingestion Pipelines

- **Synthetic Domain Generator & DNS Prober**: Generates brand + suffix + risky TLD combinations and validates live IPs via low-latency DNS resolution.
- **Certificate Transparency Logs (`crt.sh`)**: Queries real-time SSL transparency databases for instant discovery of newly issued betting mirrors.
- **Anti-Cloaking Mobile Engine**: Employs authentic Vietnamese mobile user-agents to thwart geo-cloaking.
- **Search Engine Harvester**: Harvests candidate URLs from open query streams.

---

## 5. Usage

```bash
# Run 16 concurrent bots with multi-signal evaluation and penalty deduction
python3 gambling-crawler.py --threads 16 --output suspicious_domains.txt

# Run for 15 minutes in batch mode
python3 gambling-crawler.py --threads 16 --minutes 15 --output suspicious_domains.txt
```

---

## License

MIT License.
