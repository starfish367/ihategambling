#!/usr/bin/env python3
"""
gambling-crawler.py - He thong Crawler da luong chong co bac & lua dao cong nghe cao
Nang cap kien truc:
1. Bo cham diem rui ro da tin hieu (Thang 100 diem, nguong chan >= 70):
   - Noi dung trang (40 diem): Title/Meta (15d), Body keywords (15d), APK/IPA download (10d).
   - Hanh vi chuyen huong (25 diem): HTTP 301/302 Redirect chain & JavaScript/Meta refresh redirect.
   - Cau truc ten mien (20 diem): Regex thuong hieu + so may man / nam (12d) & TLD gia re rui ro cao (8d).
   - Dau hieu ha tang (15 diem): Chat widget CSKH / Telegram (7d), Cloudflare proxy (4d), Free/New SSL cert (4d).
2. Chong Cloaking:
   - Su dung Mobile User-Agent mac dinh (iOS Safari & Android Chrome) + Header ngon ngu tieng Viet vi-VN.
3. Thu thap da kenh khong ngung nghi (Producer-Consumer):
   - Sinh to hop ten mien theo quy luat (Brand + Number/Suffix + Risky TLD) va phan giai DNS tuc thi.
   - Khai thac Certificate Transparency Logs (crt.sh).
   - Harvester tim kiem Search Engine.
   - Dao sau de quy (Harvesting link & redirect targets).
4. Whitelist tuyet doi (Khong bao gio bat nham Google, Youtube, bao chi chinh thong).
5. Zero-Emoji theo quy chuan he thong.
"""

import sys
import os
import re
import json
import time
import socket
import ssl
import random
import queue
import threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin

import requests
from bs4 import BeautifulSoup

KEYWORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keywords.json")

# Cau hinh mac dinh neu chua co keywords.json
BRAND_PREFIXES = [
    "bet", "win", "club", "casino", "vip", "ku", "th", "sh", "fb", "fun",
    "f8", "ok", "new", "jun", "hi", "bk", "w", "m", "789", "b52", "rik", "sun",
    "go", "iwin", "hit", "taixiu", "nohu", "top", "king", "soc", "vic", "zowin",
    "macau", "sin", "debet", "oxbet", "five", "red", "sky", "ta88", "lucky",
    "bong", "sbo", "saba", "cmd", "k9", "vg", "v8", "v9", "fa88", "yo88",
    "kubet", "jun88", "hi88", "shbet", "f8bet", "new88", "sunwin", "go88", "okvip", "789bet"
]

BRAND_SUFFIXES = [
    "88", "77", "99", "68", "79", "388", "888", "999", "789", "52", "188",
    "66", "365", "123", "247", "11", "22", "33", "86", "6868", "8888", "9999",
    "01", "02", "03", "04", "05", "2024", "2025", "2026", "vip", "pro", "win", "-vn", "top"
]

HIGH_RISK_TLDS = [
    ".vip", ".club", ".win", ".bet", ".top", ".xyz", ".icu", ".buzz", ".life",
    ".live", ".fun", ".site", ".online", ".cc", ".me", ".link", ".today", ".run",
    ".space", ".fit", ".rest", ".lol", ".cfd", ".sbs", ".bond", ".app", ".click"
]

HIGH_YIELD_SEARCH_QUERIES = [
    "tài xỉu online uy tín", "tải game tài xỉu đổi thưởng 2026", "tài xỉu md5 nạp rút 1-1",
    "game bài đổi thưởng uy tín", "kèo nhà cái hôm nay trực tiếp", "tỷ lệ kèo bóng đá trực tuyến",
    "baccarat trực tuyến uy tín", "kéo baccarat về bờ", "live casino trực tuyến",
    "đá gà thomo trực tiếp hôm nay", "lô đề online 1 ăn 99", "nhà cái tặng tiền trải nghiệm",
    "link vào không bị chặn mới nhất 2026", "nổ hũ jackpot đổi tiền mặt", "bắn cá đổi thưởng 2026",
    "tuyển dụng việc làm campuchia lương cao", "tuyển dụng casino bavet", "việc nhẹ lương cao mộc bài",
    "tuyển cskh campuchia bao ăn ở", "tuyển dụng casino sihanoukville", "việc làm casino chrey thum",
    "làm nhiệm vụ telegram nhận hoa hồng", "app giật đơn kiếm tiền nạp tiền shopee"
]

GAMBLING_AND_SCAM_KEYWORDS = [
    "cá cược", "cá độ", "kèo nhà cái", "tài xỉu", "tài xỉu md5", "baccarat", "casino trực tuyến",
    "đá gà thomo", "đá gà cpc", "đá gà cựa dao", "lô đề online", "bắn cá đổi thưởng", "nổ hũ",
    "game bài đổi thưởng", "xóc đĩa", "bầu cua", "rồng hổ", "sicbo", "nạp rút 1-1", "tiền cược miễn phí",
    "đăng ký nhận 88k", "link vào kubet", "link vào 789bet", "link vào shbet", "nhà cái uy tín",
    "live casino", "soi kèo", "game tài xỉu", "tải app apk ios", "việc làm campuchia",
    "việc nhẹ lương cao", "casino bavet", "casino chrey thum", "sihanoukville", "mộc bài tây ninh",
    "tuyển cskh campuchia", "tuyển telesale campuchia", "làm nhiệm vụ nhận hoa hồng", "giật đơn nhận tiền"
]

# Regex cau truc ten mien thuong hieu co bac
BRAND_REGEX = re.compile(
    r"(?:^|[\.-])([a-z0-9\-]+(?:88|77|99|68|79|388|888|789|999|52|188|365|6868|8888|202[4-9]|01|02|vip|win|pro)[a-z0-9\-]*)",
    re.IGNORECASE
)

# Nap du lieu dong tu keywords.json neu co
if os.path.exists(KEYWORDS_FILE):
    try:
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as kf:
            kdata = json.load(kf)
            if "brand_prefixes" in kdata and kdata["brand_prefixes"]:
                BRAND_PREFIXES = kdata["brand_prefixes"]
            if "brand_suffixes" in kdata and kdata["brand_suffixes"]:
                BRAND_SUFFIXES = kdata["brand_suffixes"]
            if "high_risk_tlds" in kdata and kdata["high_risk_tlds"]:
                HIGH_RISK_TLDS = kdata["high_risk_tlds"]
            if "search_queries" in kdata and kdata["search_queries"]:
                HIGH_YIELD_SEARCH_QUERIES = kdata["search_queries"]
            if "indicators" in kdata and kdata["indicators"]:
                GAMBLING_AND_SCAM_KEYWORDS = kdata["indicators"]
    except Exception:
        pass

# Whitelist tuyet doi
WHITELIST_DOMAINS = {
    "youtube.com", "youtu.be", "googlevideo.com", "google.com", "google.com.vn",
    "facebook.com", "fb.com", "messenger.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "github.com", "gitlab.com", "wikipedia.org",
    "apple.com", "microsoft.com", "cloudflare.com", "zalo.me", "tiki.vn",
    "shopee.vn", "lazada.vn", "bluestacks.com", "apkpure.com",
    # Bao chi chinh thong Viet Nam
    "vnexpress.net", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn", "24h.com.vn",
    "kenh14.vn", "zingnews.vn", "znews.vn", "baomoi.com", "vtv.vn", "vietnamnet.vn",
    "laodong.vn", "cand.com.vn", "tienphong.vn", "plo.vn", "nld.com.vn"
}

# Mobile User-Agents de chong Cloaking
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36"
]

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
]


def check_ssl_cert(domain, timeout=2.5):
    """Kiem tra nha phat hanh SSL va tuoi tho chung chi (Let's Encrypt / ZeroSSL / cap duoi 60 ngay)"""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                issuer = dict(x[0] for x in cert.get("issuer", ()))
                org = issuer.get("organizationName", "").lower()
                cn = issuer.get("commonName", "").lower()
                not_before = cert.get("notBefore")
                is_free = any(k in f"{org} {cn}" for k in ["let's encrypt", "zerossl", "google trust", "cloudflare"])
                age_days = 999
                if not_before:
                    try:
                        dt = datetime.strptime(not_before, "%b %d %H:%M:%S %Y %Z")
                        age_days = (datetime.now() - dt).days
                    except Exception:
                        pass
                return is_free or (age_days < 60)
    except Exception:
        return False


class AdvancedGamblingCrawler:
    def __init__(self, output_file="/home/a/suspicious_domains.txt", max_workers=16, use_proxy=True):
        self.output_file = os.path.abspath(output_file)
        self.max_workers = max_workers
        self.use_proxy = use_proxy
        self.proxies = []
        self.seen_domains = set()
        self.url_queue = queue.Queue(maxsize=10000)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_proxy_refresh = 0

        # Load danh sach domain da ghi nhan
        if os.path.exists(self.output_file):
            with open(self.output_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            self.seen_domains.add(parts[1].lower())

    def log(self, msg):
        now = time.strftime("%H:%M:%S")
        print(f"[{now}] {msg}", flush=True)

    def is_whitelisted(self, domain):
        domain = domain.lower()
        for wl in WHITELIST_DOMAINS:
            if domain == wl or domain.endswith("." + wl):
                return True
        return False

    def fetch_free_proxies(self):
        if not self.use_proxy:
            return
        now = time.time()
        if now - self.last_proxy_refresh < 1800 and self.proxies:
            return

        self.log("Dang cap nhat danh sach Free Proxy...")
        all_p = []
        for src in PROXY_SOURCES:
            try:
                r = requests.get(src, timeout=5)
                if r.status_code == 200:
                    lines = [p.strip() for p in r.text.splitlines() if p.strip()]
                    all_p.extend(lines)
            except Exception:
                pass
        random.shuffle(all_p)
        with self.lock:
            self.proxies = all_p
            self.last_proxy_refresh = now
        self.log(f"Da nap {len(self.proxies)} proxy vao bo dem.")

    def get_mobile_headers(self):
        return {
            "User-Agent": random.choice(MOBILE_USER_AGENTS),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Ch-Ua-Mobile": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

    def request_get(self, url, timeout=7):
        """Thuc hien HTTP GET voi Mobile User-Agent va theo doi Redirect (Uu tien IP Viet Nam truc tiep)"""
        headers = self.get_mobile_headers()
        # Uu tien ket noi truc tiep de giu nguyen IP Viet Nam (Chong Cloaking)
        try:
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if r.status_code in [200, 301, 302, 307, 308]:
                return r
        except Exception:
            pass

        # Fallback qua proxy neu ket noi truc tiep khong duoc
        if self.use_proxy and self.proxies:
            for _ in range(2):
                p = random.choice(self.proxies)
                try:
                    r = requests.get(url, headers=headers, proxies={"http": f"http://{p}", "https": f"http://{p}"}, timeout=timeout, allow_redirects=True)
                    if r.status_code in [200, 301, 302, 307, 308]:
                        return r
                except Exception:
                    pass
        return None

    def evaluate_risk_score(self, target_url, response):
        """
        Bo cham diem rui ro da tin hieu (Thang 100 diem):
        1. Noi dung trang (40d): Title/Meta (15d), Body indicators (15d), APK/IPA (10d)
        2. Hanh vi chuyen huong (25d): HTTP Redirect (15d) / JS / Meta refresh (10-15d)
        3. Cau truc ten mien (20d): Regex brand + so (12d) & High-risk TLD (8d)
        4. Dau hieu ha tang (15d): Chat widget (7d), Cloudflare (4d), Free/Recent SSL (4d)
        """
        nd_score = 0
        ch_score = 0
        tm_score = 0
        ht_score = 0
        reasons = []
        extra_urls_to_crawl = []

        parsed_orig = urlparse(target_url)
        orig_domain = parsed_orig.netloc.lower().split(":")[0]

        # ---------------------------------------------------------
        # TÍN HIỆU 3: CẤU TRÚC TÊN MIỀN (Tối đa 20 điểm)
        # ---------------------------------------------------------
        # Khớp Regex thương hiệu + số may mắn hoặc năm né chặn
        matched_brand_pattern = BRAND_REGEX.search(orig_domain)
        has_brand_prefix = any(b in orig_domain for b in BRAND_PREFIXES)
        if matched_brand_pattern or has_brand_prefix:
            tm_score += 12
            reasons.append("Pattern thuong hieu/so co bac")

        # TLD rủi ro cao giá rẻ
        has_risky_tld = any(orig_domain.endswith(tld) for tld in HIGH_RISK_TLDS)
        if has_risky_tld:
            tm_score += 8
            reasons.append("TLD rui ro cao")

        tm_score = min(20, tm_score)

        # ---------------------------------------------------------
        # TÍN HIỆU 2: HÀNH VI CHUYỂN HƯỚNG (Tối đa 25 điểm)
        # ---------------------------------------------------------
        final_domain = urlparse(response.url).netloc.lower().split(":")[0]
        if response.history:
            if final_domain != orig_domain:
                ch_score += 15
                reasons.append(f"HTTP Redirect sang {final_domain}")
                if not self.is_whitelisted(final_domain):
                    extra_urls_to_crawl.append(response.url)
            else:
                ch_score += 10
                reasons.append("HTTP Redirect noi bo")

        html_raw = response.text
        html_lower = html_raw.lower()

        # Kiểm tra JavaScript / Meta refresh redirect
        js_redirect_match = re.search(r'(?:window\.location|location\.href|location\.replace)\s*=\s*[\'"]([^\'"]+)[\'"]', html_raw)
        meta_refresh_match = re.search(r'<meta[^>]*http-equiv=[\'"]refresh[\'"][^>]*content=[\'"][^;]*;\s*url=([^\'"]+)[\'"]', html_raw, re.IGNORECASE)

        redirect_target = None
        if js_redirect_match:
            redirect_target = js_redirect_match.group(1).strip()
            reasons.append("JS Redirect")
        elif meta_refresh_match:
            redirect_target = meta_refresh_match.group(1).strip()
            reasons.append("Meta Refresh Redirect")

        if redirect_target:
            ch_score += 10
            resolved_redir = urljoin(response.url, redirect_target)
            target_dom = urlparse(resolved_redir).netloc.lower().split(":")[0]
            if target_dom and target_dom != orig_domain and not self.is_whitelisted(target_dom):
                ch_score += 5
                extra_urls_to_crawl.append(resolved_redir)

        ch_score = min(25, ch_score)

        # ---------------------------------------------------------
        # TÍN HIỆU 1: NỘI DUNG TRANG (Tối đa 40 điểm)
        # ---------------------------------------------------------
        soup = BeautifulSoup(html_raw, "html.parser")
        title_text = (soup.title.string.strip() if soup.title and soup.title.string else "").lower()
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)}) or soup.find("meta", attrs={"property": re.compile(r"og:description", re.I)})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].lower()

        header_content = f"{title_text} {meta_desc}"
        core_keywords = ["tài xỉu", "nổ hũ", "xóc đĩa", "bắn cá", "lô đề", "baccarat", "cá cược", "kèo nhà cái", "casino", "việc làm campuchia", "bavet", "chrey thum", "nhà cái uy tín", "game bài đổi thưởng"]
        matched_header = [k for k in core_keywords if k in header_content]
        if matched_header:
            nd_score += 15
            reasons.append(f"Title/Meta: {matched_header[0]}")

        # Quét Body indicators
        matched_body = [kw for kw in GAMBLING_AND_SCAM_KEYWORDS if kw in html_lower]
        if len(matched_body) >= 3:
            nd_score += 15
            reasons.append(f"Body kw ({len(matched_body)})")
        elif len(matched_body) == 2:
            nd_score += 10
        elif len(matched_body) == 1:
            nd_score += 5

        # Quét nút / liên kết tải APK / IPA
        has_app_download = bool(
            re.search(r'\.(?:apk|ipa)\b', html_raw, re.I) or
            re.search(r'(?:tải\s*(?:app|bản cài)|download\s*(?:apk|ios|app)|cài đặt app)', html_raw, re.I)
        )
        if has_app_download:
            nd_score += 10
            reasons.append("Tải bản cài APK/IPA")

        nd_score = min(40, nd_score)

        # ---------------------------------------------------------
        # TÍN HIỆU 4: DẤU HIỆU HẠ TẦNG (Tối đa 15 điểm)
        # ---------------------------------------------------------
        # Chat widgets Telegram / LiveChat / Tawk / Zalo hỗ trợ nạp tiền
        has_chat = bool(
            re.search(r'(?:t\.me/|telegram\.me/|livechatinc|tawk\.to|sp\.zalo\.me|crisp\.chat|smartsupp|comm100)', html_raw, re.I)
        )
        if has_chat:
            ht_score += 7
            reasons.append("Widget CSKH/Telegram")

        # Cloudflare header
        server_header = response.headers.get("server", "").lower()
        if "cloudflare" in server_header or "cf-ray" in response.headers:
            ht_score += 4
            reasons.append("Cloudflare Proxy")

        # Chứng chỉ SSL miễn phí / mới cấp
        if check_ssl_cert(orig_domain):
            ht_score += 4
            reasons.append("SSL Free/Moi cap")

        ht_score = min(15, ht_score)

        total_score = nd_score + ch_score + tm_score + ht_score

        # Thu hoạch link ngoại từ trang
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("http"):
                extra_urls_to_crawl.append(href)

        return total_score, nd_score, ch_score, tm_score, ht_score, reasons, extra_urls_to_crawl

    def synthetic_generator_thread(self):
        """
        Luong sinh to hop ten mien theo dung quy luat va kiem tra DNS song
        (Brand + Number/Year/Suffix + Risky TLD)
        """
        self.log("Khoi dong luong sinh to hop ten mien thong minh (Synthetic Generator)...")
        prefixes = list(BRAND_PREFIXES)
        suffixes = list(BRAND_SUFFIXES) + ["", "01", "02", "vip", "club"]
        tlds = list(HIGH_RISK_TLDS)

        while not self.stop_event.is_set():
            if self.url_queue.qsize() < 250:
                batch = []
                for _ in range(35):
                    p = random.choice(prefixes)
                    s = random.choice(suffixes)
                    t = random.choice(tlds)
                    domain_cand = f"{p}{s}{t}".lower()
                    if domain_cand not in self.seen_domains and not self.is_whitelisted(domain_cand):
                        batch.append(domain_cand)

                resolved_count = 0
                for cand in batch:
                    try:
                        # Kiem tra nhanh bang phan giai DNS
                        socket.gethostbyname(cand)
                        self.url_queue.put_nowait(f"https://{cand}")
                        resolved_count += 1
                    except Exception:
                        pass
                if resolved_count > 0:
                    self.log(f"[Synthetic] Phat hien {resolved_count} domain to hop dang HOAT DONG tren Internet -> Nap vao hang doi.")
                time.sleep(2.0)
            else:
                time.sleep(4.0)

    def crtsh_query_thread(self):
        """Luong khai thac Certificate Transparency Logs (crt.sh) theo thuong hieu"""
        self.log("Khoi dong luong Certificate Transparency Harvester (crt.sh)...")
        key_brands = ["jun88", "kubet", "hi88", "789bet", "f8bet", "new88", "shbet", "sunwin", "go88", "b52", "iwin", "okvip"]
        idx = 0

        while not self.stop_event.is_set():
            brand = key_brands[idx % len(key_brands)]
            idx += 1
            try:
                # Query domain co san duoi .com / .vip
                url = f"https://crt.sh/?q={brand}.com&output=json"
                r = requests.get(url, timeout=6)
                if r.status_code == 200:
                    data = r.json()
                    added = 0
                    for item in data[:40]:
                        nv = item.get("name_value", "")
                        for line in nv.splitlines():
                            dom = line.strip().lstrip("*.").lower()
                            if dom and dom not in self.seen_domains and not self.is_whitelisted(dom):
                                try:
                                    self.url_queue.put_nowait(f"https://{dom}")
                                    added += 1
                                except queue.Full:
                                    break
                    if added > 0:
                        self.log(f"[crt.sh] Phat hien {added} domain moi tu Certificate Logs ({brand}) -> Nap vao hang doi.")
            except Exception:
                pass
            time.sleep(15.0)

    def search_engine_thread(self):
        """Luong tim kiem web bo sung nguon URL vao hang doi"""
        self.log("Khoi dong luong tim kiem Search Engine...")
        queries = list(HIGH_YIELD_SEARCH_QUERIES)
        random.shuffle(queries)
        q_idx = 0

        while not self.stop_event.is_set():
            if self.url_queue.qsize() < 100:
                q = queries[q_idx % len(queries)]
                q_idx += 1
                try:
                    headers = self.get_mobile_headers()
                    # Query Mojeek / DuckDuckGo / Yahoo fallback
                    r = requests.get(f"https://search.yahoo.com/search?p={requests.utils.quote(q)}", headers=headers, timeout=6)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, "html.parser")
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            if "r.search.yahoo.com" in href and "/RU=" in href:
                                m = re.search(r'/RU=([^/]+)/', href)
                                if m:
                                    import urllib.parse
                                    actual = urllib.parse.unquote(m.group(1))
                                    dom = urlparse(actual).netloc.lower().split(":")[0]
                                    if dom and not self.is_whitelisted(dom) and dom not in self.seen_domains:
                                        self.url_queue.put_nowait(actual)
                except Exception:
                    pass
                time.sleep(5.0)
            else:
                time.sleep(5.0)

    def worker_thread(self, bot_id):
        """Luong xu ly danh gia 100 diem tung URL (Consumer)"""
        while not self.stop_event.is_set():
            try:
                target_url = self.url_queue.get(timeout=2.0)
            except queue.Empty:
                continue

            try:
                parsed = urlparse(target_url)
                domain = parsed.netloc.lower().split(":")[0]
                if not domain or self.is_whitelisted(domain) or domain in self.seen_domains:
                    continue

                r = self.request_get(target_url, timeout=7)
                if not r or len(r.text) < 150:
                    continue

                total, nd, ch, tm, ht, reasons, extra_links = self.evaluate_risk_score(target_url, r)

                # NGUONG CHAN: Danh dau khi Tong diem >= 70 / 100
                if total >= 70 and not self.is_whitelisted(domain):
                    with self.lock:
                        if domain not in self.seen_domains:
                            self.seen_domains.add(domain)
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            score_breakdown = f"Diem: {total}/100 (ND:{nd}, CH:{ch}, TM:{tm}, HT:{ht})"
                            reason_str = ", ".join(reasons) if reasons else "Dau hieu tong hop"
                            log_entry = f"0.0.0.0 {domain} # {timestamp} | {score_breakdown} | Ly do: {reason_str}\n"

                            with open(self.output_file, "a", encoding="utf-8") as f:
                                f.write(log_entry)

                            self.log(f"[BOT-{bot_id} PHAT HIEN] {domain} | {score_breakdown} | {reason_str}")

                    # Dao sau (Harvest) cac URL phat hien duoc
                    for link in extra_links[:15]:
                        if link.startswith("http"):
                            link_dom = urlparse(link).netloc.lower().split(":")[0]
                            if link_dom and not self.is_whitelisted(link_dom) and link_dom not in self.seen_domains:
                                try:
                                    self.url_queue.put_nowait(link)
                                except queue.Full:
                                    break
            except Exception:
                pass
            finally:
                self.url_queue.task_done()

    def run(self, max_minutes=None):
        self.log(f"Khoi dong he thong voi {self.max_workers} bot kiem tra da tin hieu (Thang 100 diem)...")
        self.fetch_free_proxies()

        # Khoi dong cac luong Harvester & Generator
        t_synth = threading.Thread(target=self.synthetic_generator_thread, daemon=True)
        t_synth.start()

        t_crt = threading.Thread(target=self.crtsh_query_thread, daemon=True)
        t_crt.start()

        t_search = threading.Thread(target=self.search_engine_thread, daemon=True)
        t_search.start()

        # Khoi dong 16 Bot Consumer
        threads = []
        for i in range(1, self.max_workers + 1):
            t = threading.Thread(target=self.worker_thread, args=(i,), daemon=True)
            t.start()
            threads.append(t)

        start_time = time.time()
        try:
            while not self.stop_event.is_set():
                time.sleep(10)
                elapsed = time.time() - start_time
                self.log(f"[Trang thai] Dang chay {self.max_workers} bot song song | Hang doi: {self.url_queue.qsize()} URL | Tong domain da xac thuc: {len(self.seen_domains)}")
                if max_minutes and (elapsed / 60.0) >= max_minutes:
                    self.log(f"Da dat thoi gian gioi han {max_minutes} phut. Dung.")
                    break
        except KeyboardInterrupt:
            self.log("Nhan tin hieu dung he thong...")
        finally:
            self.stop_event.set()


def main():
    args = sys.argv[1:]
    output_path = "/home/a/suspicious_domains.txt"
    threads = 16
    use_proxy = True
    minutes = None

    if "--output" in args:
        idx = args.index("--output")
        if len(args) > idx + 1:
            output_path = args[idx + 1]

    if "--threads" in args:
        idx = args.index("--threads")
        if len(args) > idx + 1:
            threads = int(args[idx + 1])

    if "--minutes" in args:
        idx = args.index("--minutes")
        if len(args) > idx + 1:
            minutes = float(args[idx + 1])

    if "--no-proxy" in args:
        use_proxy = False

    crawler = AdvancedGamblingCrawler(output_file=output_path, max_workers=threads, use_proxy=use_proxy)
    crawler.run(max_minutes=minutes)


if __name__ == "__main__":
    main()
