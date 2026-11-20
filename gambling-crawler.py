#!/usr/bin/env python3
"""
gambling-crawler.py - He thong Crawler da luong chong co bac & lua dao cong nghe cao
Phien ban toi uu hoa toc do, dong bo tien trinh va ghi nhan tong domain da xu ly:
1. Ghi nhan toan dien tong domain da kiem tra (Total Checked Domains):
   - Luu set checked_domains de khong bao gio quet lap lai domain cu (tranh lang phi CPU).
   - Thong ke ro rang 4 nhom: VI PHAM (>=70), NGHI NGO (40-69), An toan (<40), Offline/Chet.
2. Co che khoa tien trinh doc quyen (Singleton Process Lock - fcntl):
   - Ngan chan chay 2 script cung luc gay mat dong bo danh sach hoac xung dot ghi file.
3. Tien kiem tra TCP Socket sieu toc (Fast TCP Probe - 0.8s):
   - Loai bo 95% domain chet / cong dong trong 0.05 - 0.8s, khong lam tac nghen luong bot.
4. Kiem soat ap luc hang doi (Backpressure Control - maxsize 1500):
   - Khong cho phep hang doi phinh len 10.000 URL gay don u va ngap bo nho.
   - Luong Producer chi bom tiep khi hang doi giam xuong duoi 200 URL.
5. Bang trong so 100 diem & Co che tru diem duong tinh gia (Penalties).
6. Ghi file nguyen tu voi khoa file cap he dieu hanh (Atomic File Append & flock).
"""

import sys
import os
import re
import json
import time
import socket
import ssl
import fcntl
import random
import queue
import threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin

import requests
from bs4 import BeautifulSoup

LOCK_FILE = "/tmp/ihategambling_crawler.lock"
_lock_file_obj = None

def acquire_singleton_lock():
    """Dam bao toan he thong chi co duy nhat 1 instance crawler chay"""
    global _lock_file_obj
    try:
        _lock_file_obj = open(LOCK_FILE, "a+")
        fcntl.flock(_lock_file_obj, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file_obj.seek(0)
        _lock_file_obj.truncate()
        _lock_file_obj.write(f"{os.getpid()}\n")
        _lock_file_obj.flush()
        return True, os.getpid()
    except (IOError, BlockingIOError):
        try:
            with open(LOCK_FILE, "r") as f:
                existing_pid = f.read().strip()
        except Exception:
            existing_pid = "khong ro"
        return False, existing_pid


KEYWORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keywords.json")

BRAND_PREFIXES = [
    "bet", "win", "club", "casino", "vip", "fun88", "f8bet", "okvip", "new88", "jun88",
    "hi88", "bk8", "w88", "m88", "789bet", "b52", "rikvip", "sunwin", "go88", "iwin",
    "hitclub", "taixiu", "nohu", "top88", "kingbet", "socvip", "vicclub", "zowin",
    "macau", "sin88", "debet", "oxbet", "five88", "red88", "sky88", "ta88", "lucky88",
    "bong88", "sbobet", "saba", "cmd368", "k9vn", "v8club", "v9bet", "fa88", "yo88",
    "gem68", "manclub", "choangclub", "nagavip", "fanvip", "bancah5", "lode88", "dagathomo",
    "keonhacai", "kubet", "shbet"
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

BRAND_REGEX = re.compile(
    r"(?:kubet|sunwin|go88|789|hi88|jun88|f8bet|new88|shbet|okvip|taixiu|baccarat|xocdia|daga|nohu|m88|w88|fb88|b52|iwin)",
    re.IGNORECASE
)

REAL_MONEY_REGEX = re.compile(
    r'(?:nạp\s*rút\s*1\s*[:\-]\s*1|nạp\s*tiền|rút\s*tiền|momo|giftcode\s*tân\s*thủ|thưởng\s*nạp|nạp\s*rút\s*tự\s*động|đăng\s*ký\s*nhận\s*\d+k|hoàn\s*trả\s*cược|tiền\s*cược\s*miễn\s*phí|thưởng\s*chào\s*mừng|rút\s*về\s*ngân\s*hàng)',
    re.IGNORECASE
)

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

WHITELIST_DOMAINS = {
    "youtube.com", "youtu.be", "googlevideo.com", "google.com", "google.com.vn",
    "facebook.com", "fb.com", "messenger.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "github.com", "gitlab.com", "wikipedia.org",
    "apple.com", "microsoft.com", "cloudflare.com", "zalo.me", "tiki.vn",
    "shopee.vn", "lazada.vn", "bluestacks.com", "apkpure.com", "play.google.com", "apps.apple.com",
    "yahoo.com", "oath.com", "yimg.com", "bing.com", "msn.com", "live.com",
    # Bao chi chinh thong Viet Nam
    "vnexpress.net", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn", "24h.com.vn",
    "kenh14.vn", "zingnews.vn", "znews.vn", "baomoi.com", "vtv.vn", "vietnamnet.vn",
    "laodong.vn", "cand.com.vn", "tienphong.vn", "plo.vn", "nld.com.vn"
}

MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
]

DESKTOP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
]


def fast_tcp_probe(host, timeout=0.8):
    """Kiem tra nhanh port 443/80 co bat tay TCP hay khong de loai bo domain chet trong 0.1s"""
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return True
    except Exception:
        try:
            with socket.create_connection((host, 80), timeout=timeout):
                return True
        except Exception:
            return False


def check_ssl_cert(domain, timeout=2.0):
    """Kiem tra nha phat hanh SSL va thoi gian cap"""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                issuer = dict(x[0] for x in cert.get("issuer", ()))
                org = issuer.get("organizationName", "").lower()
                cn = issuer.get("commonName", "").lower()
                not_before = cert.get("notBefore")
                is_free_ca = any(k in f"{org} {cn}" for k in ["let's encrypt", "zerossl"])
                age_days = 999
                if not_before:
                    try:
                        dt = datetime.strptime(not_before, "%b %d %H:%M:%S %Y %Z")
                        age_days = (datetime.now() - dt).days
                    except Exception:
                        pass
                if is_free_ca and (0 <= age_days <= 30):
                    return 8, f"Free SSL ({org[:15]}) cap < 30 ngay (+8d)"
                elif is_free_ca or (0 <= age_days <= 60):
                    return 4, f"Free SSL / Cap gan day ({age_days} ngay) (+4d)"
                return 0, ""
    except Exception:
        return 0, ""


class FastAdvancedCrawler:
    def __init__(self, output_file="/home/a/suspicious_domains.txt", max_workers=16, use_proxy=True):
        self.output_file = os.path.abspath(output_file)
        self.suspect_file = os.path.join(os.path.dirname(self.output_file), "suspect_review.txt")
        self.checked_history_file = os.path.join(os.path.dirname(self.output_file), "checked_domains.txt")
        self.max_workers = max_workers
        self.use_proxy = use_proxy
        self.proxies = []

        # Danh sach phan loai
        self.violation_domains = set()
        self.suspect_domains = set()
        # Tap hop tat ca domain da kiem tra qua (de khong bao gio kiem tra lai)
        self.checked_domains = set()

        # Bo dem so luong
        self.total_checked = 0
        self.safe_count = 0
        self.dead_count = 0

        self.url_queue = queue.Queue(maxsize=1500)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_proxy_refresh = 0
        self.last_history_save = 0

        # Load domain da co
        if os.path.exists(self.output_file):
            with open(self.output_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            d = parts[1].lower()
                            self.violation_domains.add(d)
                            self.checked_domains.add(d)

        if os.path.exists(self.suspect_file):
            with open(self.suspect_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    parts = line.replace("#", "").split()
                    if len(parts) >= 2:
                        d = parts[1].lower()
                        self.suspect_domains.add(d)
                        self.checked_domains.add(d)

        if os.path.exists(self.checked_history_file):
            with open(self.checked_history_file, "r", encoding="utf-8") as f:
                for line in f:
                    d = line.strip().lower()
                    if d:
                        self.checked_domains.add(d)

        self.total_checked = len(self.checked_domains)

    def log(self, msg):
        now = time.strftime("%H:%M:%S")
        print(f"[{now}] {msg}", flush=True)

    def is_whitelisted(self, domain, html=""):
        domain = domain.lower()
        if domain.endswith(".gov.vn") or domain.endswith(".edu.vn") or domain.endswith(".gov") or domain.endswith(".edu"):
            return True
        if html and "online.gov.vn" in html:
            return True
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
                r = requests.get(src, timeout=4)
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

    def request_get(self, url, timeout=3.5):
        headers = self.get_mobile_headers()
        try:
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if r.status_code in [200, 301, 302, 307, 308]:
                return r
            if r.status_code == 403 and self.use_proxy and self.proxies:
                p = random.choice(self.proxies)
                return requests.get(url, headers=headers, proxies={"http": f"http://{p}", "https": f"http://{p}"}, timeout=timeout, allow_redirects=True)
        except Exception:
            pass
        return None

    def check_cloaking(self, url, mobile_len):
        try:
            headers = {
                "User-Agent": DESKTOP_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            r_desk = requests.get(url, headers=headers, timeout=3.0, allow_redirects=True)
            if r_desk.status_code in [403, 404]:
                return True
            desk_len = len(r_desk.text)
            diff_ratio = abs(mobile_len - desk_len) / max(mobile_len, desk_len, 1)
            if diff_ratio > 0.5:
                return True
        except Exception:
            pass
        return False

    def evaluate_risk_score(self, target_url, response):
        nd_score = 0
        ch_score = 0
        tm_score = 0
        ht_score = 0
        penalty_score = 0
        reasons = []
        extra_urls_to_crawl = []

        parsed_orig = urlparse(target_url)
        orig_domain = parsed_orig.netloc.lower().split(":")[0]
        html_raw = response.text
        soup = BeautifulSoup(html_raw, "html.parser")

        # Pre-filter
        if self.is_whitelisted(orig_domain, html_raw):
            return 0, 0, 0, 0, 0, 0, ["Whitelist / Chinh phu / Bo Cong Thuong"], []

        # Nhom 3: Ten mien (20d)
        has_brand = bool(BRAND_REGEX.search(orig_domain)) or any(b in orig_domain for b in BRAND_PREFIXES if len(b) >= 4)
        if has_brand:
            tm_score += 12
            reasons.append("Thuong hieu/so co bac (+12d)")

        has_risky_tld = any(orig_domain.endswith(tld) for tld in HIGH_RISK_TLDS)
        if has_risky_tld:
            tm_score += 8
            reasons.append("TLD rui ro cao (+8d)")

        tm_score = min(20, tm_score)

        # Nhom 2: Chuyen huong & Cloaking (25d)
        final_domain = urlparse(response.url).netloc.lower().split(":")[0]
        has_cross_redirect = False

        if response.history:
            if final_domain != orig_domain:
                ch_score += 15
                has_cross_redirect = True
                reasons.append(f"HTTP Redirect sang {final_domain} (+15d)")
                if not self.is_whitelisted(final_domain) and final_domain not in self.checked_domains:
                    extra_urls_to_crawl.append(response.url)
            else:
                ch_score += 10
                reasons.append("HTTP Redirect noi bo (+10d)")

        js_redirect_match = re.search(r'(?:window\.location|location\.href|location\.replace)\s*=\s*[\'"]([^\'"]+)[\'"]', html_raw)
        meta_refresh_match = re.search(r'<meta[^>]*http-equiv=[\'"]refresh[\'"][^>]*content=[\'"][^;]*;\s*url=([^\'"]+)[\'"]', html_raw, re.IGNORECASE)

        redirect_target = None
        if js_redirect_match:
            redirect_target = js_redirect_match.group(1).strip()
        elif meta_refresh_match:
            redirect_target = meta_refresh_match.group(1).strip()

        if redirect_target:
            resolved_redir = urljoin(response.url, redirect_target)
            target_dom = urlparse(resolved_redir).netloc.lower().split(":")[0]
            if target_dom and target_dom != orig_domain:
                if not has_cross_redirect:
                    ch_score += 15
                    has_cross_redirect = True
                reasons.append(f"JS/Meta Redirect sang {target_dom} (+15d)")
                if not self.is_whitelisted(target_dom) and target_dom not in self.checked_domains:
                    extra_urls_to_crawl.append(resolved_redir)
            elif ch_score == 0:
                ch_score += 10
                reasons.append("JS Redirect noi bo (+10d)")

        if self.check_cloaking(target_url, len(html_raw)):
            ch_score += 10
            reasons.append("Cloaking Mobile vs Desktop (+10d)")

        ch_score = min(25, ch_score)

        # Nhom 1: Noi dung & UI (40d)
        title_text = (soup.title.string.strip() if soup.title and soup.title.string else "").lower()
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)}) or soup.find("meta", attrs={"property": re.compile(r"og:description", re.I)})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].lower()

        head_elements = [title_text, meta_desc]
        for h_tag in soup.find_all(["h1", "h2", "h3"]):
            head_elements.append(h_tag.get_text().strip().lower())
        combined_head = " ".join(head_elements)

        core_kws = ["nổ hũ", "tài xỉu", "xóc đĩa", "lô đề", "baccarat", "cá cược", "kèo nhà cái", "bắn cá", "casino", "game bài đổi thưởng"]
        kw_density_count = sum(len(re.findall(re.escape(k), combined_head, re.I)) for k in core_kws)
        if kw_density_count >= 5:
            nd_score += 15
            reasons.append(f"Tu khoa co bac mat do cao ({kw_density_count} lan, +15d)")
        elif kw_density_count >= 1:
            nd_score += 8
            reasons.append(f"Tu khoa tieu de/H1-H3 ({kw_density_count} lan, +8d)")

        cta_elements = soup.find_all(["button", "a", "input"])
        cta_texts = [el.get_text().strip() for el in cta_elements if el.name != "input"]
        cta_texts += [el.get("value", "") for el in cta_elements if el.name == "input"]
        has_real_money_cta = any(REAL_MONEY_REGEX.search(txt) for txt in cta_texts) or bool(REAL_MONEY_REGEX.search(combined_head))
        if has_real_money_cta:
            nd_score += 15
            reasons.append("Cum tu giao dich tien that nut/banner (+15d)")

        sideload_app = False
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip().lower()
            if re.search(r'\.(?:apk|ipa|mobileconfig)\b', href) or "download/apk" in href or "ios/profile" in href:
                sideload_app = True
                break
        if not sideload_app:
            if re.search(r'(?:tải\s*(?:bản cài|file)\s*apk|cài\s*đặt\s*cấu\s*hình\s*ios|tải\s*ipa)', html_raw, re.I):
                sideload_app = True

        if sideload_app:
            nd_score += 10
            reasons.append("Link tai app ngoai luong APK/IPA/iOS config (+10d)")

        nd_score = min(40, nd_score)

        # Nhom 4: Ha tang (15d)
        ssl_score, ssl_reason = check_ssl_cert(orig_domain)
        if ssl_score > 0:
            ht_score += ssl_score
            reasons.append(ssl_reason)

        has_direct_support = bool(
            re.search(r'(?:t\.me/|telegram\.me/|livechatinc|tawk\.to|crisp\.chat|smartsupp|comm100)', html_raw, re.I)
        )
        if has_direct_support:
            ht_score += 7
            reasons.append("Widget LiveChat/Telegram ho tro nap rut (+7d)")

        ht_score = min(15, ht_score)

        # Co che tru diem (Penalties)
        article_elem = soup.find("article") or soup.find("main") or soup.find("body")
        article_text = article_elem.get_text() if article_elem else soup.get_text()
        words = re.findall(r'\b\w+\b', article_text)

        has_auth_form = bool(
            soup.find("form") and (
                soup.find("input", attrs={"type": "password"}) or
                re.search(r'(?:đăng\s*ký|đăng\s*nhập|register|login)', soup.text, re.I)
            )
        )
        has_deposit_action = bool(re.search(r'(?:nạp\s*tiền|rút\s*tiền|nạp\s*rút|thưởng\s*nạp)', soup.text, re.I))

        if len(words) >= 800 and not has_auth_form and not has_deposit_action:
            penalty_score += 35
            reasons.append(f"Tru: Bai bao tin tuc canh bao ({len(words)} tu, -35d)")

        has_official_appstore = False
        for a_tag in soup.find_all("a", href=True):
            href_val = a_tag["href"].strip().lower()
            if "play.google.com/store" in href_val or "apps.apple.com" in href_val:
                has_official_appstore = True
                break
        if has_official_appstore and not sideload_app:
            penalty_score += 30
            reasons.append("Tru: Kho ung dung chinh thong Google Play / App Store (-30d)")

        footer_elem = soup.find("footer") or soup.find("div", class_=re.compile(r"footer", re.I))
        footer_text = footer_elem.get_text() if footer_elem else html_raw[-4000:]

        mst_match = re.search(r'(?:mã\s*số\s*thuế|mst|tax\s*code|m\.s\.t|đkkd|gpdkkd)\s*[:.]?\s*(\d{10}(?:-\d{3})?)', footer_text, re.I)
        has_vn_address = bool(re.search(r'(?:địa\s*chỉ|trụ\s*sở|tầng\s*\d+|phường|quận|huyện|thành\s*phố|tp\.|hà\s*nội|hồ\s*chí\s*minh|đà\s*nẵng|việt\s*nam)', footer_text, re.I))

        if mst_match and has_vn_address and (ch_score == 0):
            penalty_score += 25
            reasons.append(f"Tru: Doanh nghiep hop phap/MST: {mst_match.group(1)} (-25d)")

        raw_score = nd_score + ch_score + tm_score + ht_score
        total_score = max(0, min(100, raw_score - penalty_score))

        # Thu hoach link ngoai: chi thu hoach neu trang dang ngo hoac vi pham
        if total_score >= 40:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if href.startswith("http"):
                    extra_urls_to_crawl.append(href)
                    if len(extra_urls_to_crawl) >= 3:
                        break

        return total_score, nd_score, ch_score, tm_score, ht_score, penalty_score, reasons, extra_urls_to_crawl

    def atomic_append_file(self, filepath, line):
        with open(filepath, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(line)
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

    def save_checked_history(self):
        """Dinh ky luu tap hop checked_domains de khoi dong lai khong bi trung lap"""
        now = time.time()
        if now - self.last_history_save < 60:
            return
        with self.lock:
            self.last_history_save = now
            doms = list(self.checked_domains)
        try:
            with open(self.checked_history_file, "w", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for d in doms[-30000:]:
                    f.write(f"{d}\n")
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            pass

    def synthetic_generator_thread(self):
        """Luong sinh to hop ten mien - Chi sinh khi hang doi < 200 URL (Chong ngap)"""
        self.log("Khoi dong luong sinh to hop ten mien thong minh (Synthetic Generator)...")
        prefixes = list(BRAND_PREFIXES)
        suffixes = list(BRAND_SUFFIXES) + ["", "01", "02", "vip"]
        tlds = list(HIGH_RISK_TLDS)

        while not self.stop_event.is_set():
            if self.url_queue.qsize() < 200:
                batch = []
                for _ in range(25):
                    p = random.choice(prefixes)
                    s = random.choice(suffixes)
                    t = random.choice(tlds)
                    domain_cand = f"{p}{s}{t}".lower()
                    if domain_cand not in self.checked_domains and not self.is_whitelisted(domain_cand):
                        batch.append(domain_cand)

                resolved_count = 0
                for cand in batch:
                    if fast_tcp_probe(cand, timeout=0.8):
                        try:
                            self.url_queue.put_nowait(f"https://{cand}")
                            resolved_count += 1
                        except queue.Full:
                            break
                    else:
                        with self.lock:
                            self.checked_domains.add(cand)
                            self.dead_count += 1
                            self.total_checked += 1

                if resolved_count > 0:
                    self.log(f"[Synthetic] Nap {resolved_count} domain to hop CO PHAN HOI TCP vao hang doi.")
                time.sleep(1.5)
            else:
                time.sleep(3.0)

    def crtsh_query_thread(self):
        """Luong Certificate Transparency Logs - Dieu tiet toc do tranh don hang doi"""
        self.log("Khoi dong luong Certificate Transparency Harvester (crt.sh)...")
        key_brands = ["jun88", "kubet", "hi88", "789bet", "f8bet", "new88", "shbet", "sunwin", "go88", "b52", "iwin", "okvip"]
        idx = 0

        while not self.stop_event.is_set():
            if self.url_queue.qsize() < 300:
                brand = key_brands[idx % len(key_brands)]
                idx += 1
                try:
                    url = f"https://crt.sh/?q={brand}.com&output=json"
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        added = 0
                        for item in data[:20]:
                            nv = item.get("name_value", "")
                            for line in nv.splitlines():
                                dom = line.strip().lstrip("*.").lower()
                                if dom and dom not in self.checked_domains and not self.is_whitelisted(dom):
                                    if fast_tcp_probe(dom, timeout=0.8):
                                        try:
                                            self.url_queue.put_nowait(f"https://{dom}")
                                            added += 1
                                        except queue.Full:
                                            break
                                    else:
                                        with self.lock:
                                            self.checked_domains.add(dom)
                                            self.dead_count += 1
                                            self.total_checked += 1
                        if added > 0:
                            self.log(f"[crt.sh] Phat hien {added} domain moi co web server song ({brand}) -> Nap vao hang doi.")
                except Exception:
                    pass
                time.sleep(20.0)
            else:
                time.sleep(5.0)

    def search_engine_thread(self):
        """Luong tim kiem web - Dieu tiet nhan nhe"""
        self.log("Khoi dong luong tim kiem Search Engine...")
        queries = list(HIGH_YIELD_SEARCH_QUERIES)
        random.shuffle(queries)
        q_idx = 0

        while not self.stop_event.is_set():
            if self.url_queue.qsize() < 250:
                q = queries[q_idx % len(queries)]
                q_idx += 1
                try:
                    headers = self.get_mobile_headers()
                    r = requests.get(f"https://search.yahoo.com/search?p={requests.utils.quote(q)}", headers=headers, timeout=5)
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
                                    if dom and not self.is_whitelisted(dom) and dom not in self.checked_domains:
                                        if fast_tcp_probe(dom, timeout=0.8):
                                            self.url_queue.put_nowait(actual)
                                        else:
                                            with self.lock:
                                                self.checked_domains.add(dom)
                                                self.dead_count += 1
                                                self.total_checked += 1
                except Exception:
                    pass
                time.sleep(8.0)
            else:
                time.sleep(5.0)

    def worker_thread(self, bot_id):
        """Luong bot xu ly sieu toc voi TCP pre-check va cap nhat tong domain da xu ly"""
        while not self.stop_event.is_set():
            try:
                target_url = self.url_queue.get(timeout=1.5)
            except queue.Empty:
                continue

            try:
                parsed = urlparse(target_url)
                domain = parsed.netloc.lower().split(":")[0]
                if not domain or self.is_whitelisted(domain):
                    continue

                with self.lock:
                    if domain in self.checked_domains:
                        continue
                    # Ghi nhan ngay vao tap hop domain da kiem tra
                    self.checked_domains.add(domain)

                # 1. Kiem tra nhanh TCP Probe (0.8s)
                if not fast_tcp_probe(domain, timeout=0.8):
                    with self.lock:
                        self.dead_count += 1
                        self.total_checked += 1
                    continue

                r = self.request_get(target_url, timeout=3.5)
                if not r or len(r.text) < 150:
                    with self.lock:
                        self.dead_count += 1
                        self.total_checked += 1
                    continue

                total, nd, ch, tm, ht, penalty, reasons, extra_links = self.evaluate_risk_score(target_url, r)

                with self.lock:
                    self.total_checked += 1

                # 1. 70 - 100 diem: VI PHAM
                if total >= 70 and not self.is_whitelisted(domain):
                    with self.lock:
                        if domain not in self.violation_domains:
                            self.violation_domains.add(domain)
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            score_breakdown = f"VI PHAM ({total}/100) [ND:{nd}, CH:{ch}, TM:{tm}, HT:{ht}, Tru:{penalty}]"
                            reason_str = ", ".join(reasons) if reasons else "Dau hieu tong hop"
                            log_entry = f"0.0.0.0 {domain} # {timestamp} | {score_breakdown} | Ly do: {reason_str}\n"

                            self.atomic_append_file(self.output_file, log_entry)
                            self.log(f"[BOT-{bot_id} VI PHAM] {domain} | {score_breakdown} | {reason_str}")

                # 2. 40 - 69 diem: NGHI NGO
                elif 40 <= total < 70 and not self.is_whitelisted(domain):
                    with self.lock:
                        if domain not in self.suspect_domains:
                            self.suspect_domains.add(domain)
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            score_breakdown = f"NGHI NGO ({total}/100) [ND:{nd}, CH:{ch}, TM:{tm}, HT:{ht}, Tru:{penalty}]"
                            reason_str = ", ".join(reasons) if reasons else "Dau hieu nghi ngo"
                            log_entry = f"# 0.0.0.0 {domain} # {timestamp} | {score_breakdown} | Ly do: {reason_str}\n"

                            self.atomic_append_file(self.suspect_file, log_entry)
                            self.log(f"[BOT-{bot_id} NGHI NGO] {domain} | {score_breakdown} | {reason_str}")

                # 3. Duoi 40 diem: AN TOAN
                else:
                    with self.lock:
                        self.safe_count += 1

                # Dao sau link thu hoach (chi lay link tu trang nghi ngo/vi pham)
                for link in extra_links:
                    link_dom = urlparse(link).netloc.lower().split(":")[0]
                    if link_dom and not self.is_whitelisted(link_dom) and link_dom not in self.checked_domains:
                        try:
                            self.url_queue.put_nowait(link)
                        except queue.Full:
                            break
            except Exception:
                pass
            finally:
                self.url_queue.task_done()

    def run(self, max_minutes=None):
        self.log(f"Khoi dong he thong voi {self.max_workers} bot xu ly sieu toc (Ghi nhan toan dien tong domain da xu ly)...")
        self.fetch_free_proxies()

        t_synth = threading.Thread(target=self.synthetic_generator_thread, daemon=True)
        t_synth.start()

        t_crt = threading.Thread(target=self.crtsh_query_thread, daemon=True)
        t_crt.start()

        t_search = threading.Thread(target=self.search_engine_thread, daemon=True)
        t_search.start()

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
                self.save_checked_history()
                self.log(
                    f"[Trang thai] Da kiem tra: {self.total_checked} domain "
                    f"(VI PHAM: {len(self.violation_domains)}, NGHI NGO: {len(self.suspect_domains)}, An toan: {self.safe_count}, Offline: {self.dead_count}) "
                    f"| Hang doi: {self.url_queue.qsize()}/1500 URL"
                )
                if max_minutes and (elapsed / 60.0) >= max_minutes:
                    self.log(f"Da dat thoi gian gioi han {max_minutes} phut. Dung.")
                    break
        except KeyboardInterrupt:
            self.log("Nhan tin hieu dung he thong...")
        finally:
            self.stop_event.set()
            self.save_checked_history()


def main():
    success, pid_info = acquire_singleton_lock()
    if not success:
        print(f"[CANH BAO DONG BO] Da co mot tien trinh crawler khac dang chay tren he thong (PID: {pid_info}).")
        print("He thong chi cho phep chay dung 1 script duy nhat de dong bo danh sach seen_domains va tranh xung dot ghi file.")
        print(f"Neu muon khoi dong lai, hay tat tien trinh cu bang: kill -9 {pid_info}")
        sys.exit(0)

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

    crawler = FastAdvancedCrawler(output_file=output_path, max_workers=threads, use_proxy=use_proxy)
    crawler.run(max_minutes=minutes)


if __name__ == "__main__":
    main()
