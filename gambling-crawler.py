#!/usr/bin/env python3
"""
gambling-crawler.py - He thong Crawler da luong chong co bac & lua dao cong nghe cao
Nang cap kien truc:
1. Bang trong so cham diem chi tiet (Thang 100 diem):
   - Nhom Noi dung & UI (40d):
     * Tu khoa co bac mat do cao (>= 5 lan trong title, meta, h1-h3): +15d
     * Cum tu giao dich tien that (nap rut 1:1, momo, giftcode tan thu): +15d
     * Link tai ung dung ngoai luong (.apk, .ipa, iOS config): +10d
   - Nhom Chuyen huong (25d):
     * Chuyen huong tu dong (HTTP 301/302 hoac JS redirect sang domain khac): +15d
     * Ky thuat che giau (Cloaking - chenh lech Mobile VN vs Desktop/ngoai): +10d
   - Nhom Ten mien (20d):
     * Thuong hieu hoac so dac trung (kubet, sunwin, go88, 789, hi88, jun88, tx, nohu, bet...): +12d
     * Duoi ten mien (TLD) rui ro cao (.vip, .club, .win, .bet, .top, .xyz, .icu...): +8d
   - Nhom Ha tang (15d):
     * Chung chi SSL mien phi moi cap (< 30 ngay, Let's Encrypt / ZeroSSL): +8d
     * Kenh ho tro nap rut truc tiep (Widget LiveChat hoac link t.me/): +7d
2. Bo loc truoc (Pre-filter) va Co che tru diem xu ly duong tinh gia:
   - Bo qua ten mien co quan nha nuoc (.gov.vn), giao duc (.edu.vn), logo xac thuc Bo Cong Thuong (online.gov.vn).
   - Nhan dien bai bao tin tuc canh bao (-35d): > 800 tu, khong form dang ky, khong nut nap tien.
   - Kiem tra kho ung dung chinh thong (-30d): Nut tai app tro ve play.google.com hoac apps.apple.com.
   - Xac minh thong tin doanh nghiep hop phap (-25d): Ma so thue (MST) hop le, dia chi VN tai footer, khong redirect an.
3. Thang danh gia phan loai:
   - 70 - 100 diem: Xac nhan trang co bac / no hu vi pham (ghi vao suspicious_domains.txt).
   - 40 - 69 diem: Vung nghi ngo (ghi vao suspect_review.txt de hau kiem).
   - Duoi 40 diem: Trang an toan hoac khong du dau hieu ket luan.
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

# Regex thuong hieu co bac
BRAND_REGEX = re.compile(
    r"(?:kubet|sunwin|go88|789|hi88|jun88|tx|nohu|bet|b52|iwin|shbet|f8bet|new88|okvip|taixiu|baccarat|xocdia|daga)",
    re.IGNORECASE
)

# Regex cum tu giao dich tien that tren nut bam/banner
REAL_MONEY_REGEX = re.compile(
    r'(?:nạp\s*rút\s*1\s*[:\-]\s*1|nạp\s*tiền|rút\s*tiền|momo|giftcode\s*tân\s*thủ|thưởng\s*nạp|nạp\s*rút\s*tự\s*động|đăng\s*ký\s*nhận\s*\d+k|hoàn\s*trả\s*cược|tiền\s*cược\s*miễn\s*phí|thưởng\s*chào\s*mừng|rút\s*về\s*ngân\s*hàng)',
    re.IGNORECASE
)

# Nap tu keywords.json neu co
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

# Whitelist co ban
WHITELIST_DOMAINS = {
    "youtube.com", "youtu.be", "googlevideo.com", "google.com", "google.com.vn",
    "facebook.com", "fb.com", "messenger.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "github.com", "gitlab.com", "wikipedia.org",
    "apple.com", "microsoft.com", "cloudflare.com", "zalo.me", "tiki.vn",
    "shopee.vn", "lazada.vn", "bluestacks.com", "apkpure.com", "play.google.com", "apps.apple.com",
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


def check_ssl_cert(domain, timeout=2.5):
    """
    Kiem tra chung chi SSL mien phi (Let's Encrypt / ZeroSSL) moi cap duoi 30 ngay (+8d)
    hoac chung chi ngan han khac (+4d).
    """
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


class AdvancedGamblingCrawler:
    def __init__(self, output_file="/home/a/suspicious_domains.txt", max_workers=16, use_proxy=True):
        self.output_file = os.path.abspath(output_file)
        self.suspect_file = os.path.join(os.path.dirname(self.output_file), "suspect_review.txt")
        self.max_workers = max_workers
        self.use_proxy = use_proxy
        self.proxies = []
        self.seen_domains = set()
        self.url_queue = queue.Queue(maxsize=10000)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_proxy_refresh = 0

        # Load danh sach domain da ghi nhan
        for fpath in [self.output_file, self.suspect_file]:
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split()
                            if len(parts) >= 2:
                                self.seen_domains.add(parts[1].lower())

    def log(self, msg):
        now = time.strftime("%H:%M:%S")
        print(f"[{now}] {msg}", flush=True)

    def is_whitelisted(self, domain, html=""):
        """
        Bo loc truoc (Pre-filter):
        - Bo qua co quan nha nuoc (.gov.vn, .gov)
        - Bo qua giao duc (.edu.vn, .edu)
        - Bo qua trang co tich xac thuc Bo Cong Thuong (online.gov.vn)
        - Bo qua cac trang lon trong whitelist
        """
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
        try:
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if r.status_code in [200, 301, 302, 307, 308]:
                return r
        except Exception:
            pass

        # Fallback qua proxy neu ket noi truc tiep bi chan
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

    def check_cloaking(self, url, mobile_len):
        """
        Kiem tra ky thuat che giau (Cloaking):
        Gui them 1 request nhe voi Desktop UA. Neu tra ve loi hoac do dai chenh lech > 50% -> Phat hien Cloaking (+10d)
        """
        try:
            headers = {
                "User-Agent": DESKTOP_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            r_desk = requests.get(url, headers=headers, timeout=4, allow_redirects=True)
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
        """
        Bang trong so cham diem 100 diem va Co che tru diem xu ly duong tinh gia
        """
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
        html_lower = html_raw.lower()
        soup = BeautifulSoup(html_raw, "html.parser")

        # ---------------------------------------------------------
        # PRE-FILTER: Kiem tra danh sach trang / Co quan nha nuoc / BCT
        # ---------------------------------------------------------
        if self.is_whitelisted(orig_domain, html_raw):
            return 0, 0, 0, 0, 0, 0, ["Trang trong Whitelist / Chinh phu / Bo Cong Thuong"], []

        # ---------------------------------------------------------
        # NHOM 3: TEN MIEN (Toi da 20 diem)
        # ---------------------------------------------------------
        # Khop Regex thuong hieu hoac so dac trung (+12d)
        has_brand = bool(BRAND_REGEX.search(orig_domain)) or any(b in orig_domain for b in BRAND_PREFIXES)
        if has_brand:
            tm_score += 12
            reasons.append("Thuong hieu/so co bac (+12d)")

        # Duoi ten mien TLD rui ro cao (+8d)
        has_risky_tld = any(orig_domain.endswith(tld) for tld in HIGH_RISK_TLDS)
        if has_risky_tld:
            tm_score += 8
            reasons.append("TLD rui ro cao (+8d)")

        tm_score = min(20, tm_score)

        # ---------------------------------------------------------
        # NHOM 2: CHUYEN HUONG & CLOAKING (Toi da 25 diem)
        # ---------------------------------------------------------
        # Chuyen huong tu dong (HTTP 301/302 hoac JS) sang ten mien khac (+15d)
        final_domain = urlparse(response.url).netloc.lower().split(":")[0]
        has_cross_redirect = False

        if response.history:
            if final_domain != orig_domain:
                ch_score += 15
                has_cross_redirect = True
                reasons.append(f"HTTP Redirect sang {final_domain} (+15d)")
                if not self.is_whitelisted(final_domain):
                    extra_urls_to_crawl.append(response.url)
            else:
                ch_score += 10
                reasons.append("HTTP Redirect noi bo (+10d)")

        # Kiem tra JavaScript / Meta refresh redirect
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
                if not self.is_whitelisted(target_dom):
                    extra_urls_to_crawl.append(resolved_redir)
            elif ch_score == 0:
                ch_score += 10
                reasons.append("JS Redirect noi bo (+10d)")

        # Ky thuat che giau (Cloaking) (+10d)
        if self.check_cloaking(target_url, len(html_raw)):
            ch_score += 10
            reasons.append("Cloaking Mobile vs Desktop (+10d)")

        ch_score = min(25, ch_score)

        # ---------------------------------------------------------
        # NHOM 1: NOI DUNG & UI (Toi da 40 diem)
        # ---------------------------------------------------------
        title_text = (soup.title.string.strip() if soup.title and soup.title.string else "").lower()
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)}) or soup.find("meta", attrs={"property": re.compile(r"og:description", re.I)})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].lower()

        # Thu thap noi dung tieu de va h1-h3
        head_elements = [title_text, meta_desc]
        for h_tag in soup.find_all(["h1", "h2", "h3"]):
            head_elements.append(h_tag.get_text().strip().lower())
        combined_head = " ".join(head_elements)

        # Tu khoa co bac mat do cao: xuat hien tu 5 lan tro len trong title, meta, h1-h3 (+15d)
        core_kws = ["nổ hũ", "tài xỉu", "xóc đĩa", "lô đề", "baccarat", "cá cược", "kèo nhà cái", "bắn cá", "casino", "game bài đổi thưởng"]
        kw_density_count = sum(len(re.findall(re.escape(k), combined_head, re.I)) for k in core_kws)
        if kw_density_count >= 5:
            nd_score += 15
            reasons.append(f"Tu khoa co bac mat do cao ({kw_density_count} lan, +15d)")
        elif kw_density_count >= 1:
            nd_score += 8
            reasons.append(f"Tu khoa tieu de/H1-H3 ({kw_density_count} lan, +8d)")

        # Cum tu giao dich tien that tren nut bam / banner / link (+15d)
        cta_elements = soup.find_all(["button", "a", "input"])
        cta_texts = [el.get_text().strip() for el in cta_elements if el.name != "input"]
        cta_texts += [el.get("value", "") for el in cta_elements if el.name == "input"]
        has_real_money_cta = any(REAL_MONEY_REGEX.search(txt) for txt in cta_texts) or bool(REAL_MONEY_REGEX.search(combined_head))
        if has_real_money_cta:
            nd_score += 15
            reasons.append("Cum tu giao dich tien that nut/banner (+15d)")

        # Link tai ung dung ngoai luong (.apk, .ipa, iOS config profile) (+10d)
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

        # ---------------------------------------------------------
        # NHOM 4: HA TANG (Toi da 15 diem)
        # ---------------------------------------------------------
        # Chung chi SSL mien phi moi cap duoi 30 ngay (+8d)
        ssl_score, ssl_reason = check_ssl_cert(orig_domain)
        if ssl_score > 0:
            ht_score += ssl_score
            reasons.append(ssl_reason)

        # Kenh ho tro nap rut truc tiep: Widget LiveChat hoac t.me/ (+7d)
        has_direct_support = bool(
            re.search(r'(?:t\.me/|telegram\.me/|livechatinc|tawk\.to|crisp\.chat|smartsupp|comm100)', html_raw, re.I)
        )
        if has_direct_support:
            ht_score += 7
            reasons.append("Widget LiveChat/Telegram ho tro nap rut (+7d)")

        ht_score = min(15, ht_score)

        # ---------------------------------------------------------
        # CO CHE TRU DIEM XU LY DUONG TINH GIA (PENALTIES)
        # ---------------------------------------------------------
        # 1. Nhan dien bai bao tin tuc canh bao (-35d)
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

        # 2. Kiem tra kho ung dung chinh thong (-30d)
        has_official_appstore = False
        for a_tag in soup.find_all("a", href=True):
            href_val = a_tag["href"].strip().lower()
            if "play.google.com/store" in href_val or "apps.apple.com" in href_val:
                has_official_appstore = True
                break
        if has_official_appstore and not sideload_app:
            penalty_score += 30
            reasons.append("Tru: Kho ung dung chinh thong Google Play / App Store (-30d)")

        # 3. Xac minh thong tin doanh nghiep hop phap (-25d)
        footer_elem = soup.find("footer") or soup.find("div", class_=re.compile(r"footer", re.I))
        footer_text = footer_elem.get_text() if footer_elem else html_raw[-4000:]

        mst_match = re.search(r'(?:mã\s*số\s*thuế|mst|tax\s*code|m\.s\.t|đkkd|gpdkkd)\s*[:.]?\s*(\d{10}(?:-\d{3})?)', footer_text, re.I)
        has_vn_address = bool(re.search(r'(?:địa\s*chỉ|trụ\s*sở|tầng\s*\d+|phường|quận|huyện|thành\s*phố|tp\.|hà\s*nội|hồ\s*chí\s*minh|đà\s*nẵng|việt\s*nam)', footer_text, re.I))

        if mst_match and has_vn_address and (ch_score == 0):
            penalty_score += 25
            reasons.append(f"Tru: Doanh nghiep hop phap/MST: {mst_match.group(1)} (-25d)")

        # Tinh tong diem cuoi cung sau khi ap dung diem tru
        raw_score = nd_score + ch_score + tm_score + ht_score
        total_score = max(0, min(100, raw_score - penalty_score))

        # Thu hoach link ngoai de quet sau
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("http"):
                extra_urls_to_crawl.append(href)

        return total_score, nd_score, ch_score, tm_score, ht_score, penalty_score, reasons, extra_urls_to_crawl

    def synthetic_generator_thread(self):
        """Luong sinh to hop ten mien theo quy luat va kiem tra DNS song"""
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
        """Luong Certificate Transparency Logs (crt.sh)"""
        self.log("Khoi dong luong Certificate Transparency Harvester (crt.sh)...")
        key_brands = ["jun88", "kubet", "hi88", "789bet", "f8bet", "new88", "shbet", "sunwin", "go88", "b52", "iwin", "okvip"]
        idx = 0

        while not self.stop_event.is_set():
            brand = key_brands[idx % len(key_brands)]
            idx += 1
            try:
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
        """Luong xu ly danh gia phan loai tung URL (Consumer)"""
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

                total, nd, ch, tm, ht, penalty, reasons, extra_links = self.evaluate_risk_score(target_url, r)

                # THANG DANH GIA PHAN LOAI:
                # 1. 70 - 100 diem: Xac nhan trang co bac / no hu vi pham (gan nhan chan)
                if total >= 70 and not self.is_whitelisted(domain):
                    with self.lock:
                        if domain not in self.seen_domains:
                            self.seen_domains.add(domain)
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            score_breakdown = f"VI PHAM ({total}/100) [ND:{nd}, CH:{ch}, TM:{tm}, HT:{ht}, Tru:{penalty}]"
                            reason_str = ", ".join(reasons) if reasons else "Dau hieu tong hop"
                            log_entry = f"0.0.0.0 {domain} # {timestamp} | {score_breakdown} | Ly do: {reason_str}\n"

                            with open(self.output_file, "a", encoding="utf-8") as f:
                                f.write(log_entry)

                            self.log(f"[BOT-{bot_id} VI PHAM] {domain} | {score_breakdown} | {reason_str}")

                # 2. 40 - 69 diem: Vung nghi ngo (luu lai de hau kiem)
                elif 40 <= total < 70 and not self.is_whitelisted(domain):
                    with self.lock:
                        if domain not in self.seen_domains:
                            self.seen_domains.add(domain)
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            score_breakdown = f"NGHI NGO ({total}/100) [ND:{nd}, CH:{ch}, TM:{tm}, HT:{ht}, Tru:{penalty}]"
                            reason_str = ", ".join(reasons) if reasons else "Dau hieu nghi ngo"
                            log_entry = f"# 0.0.0.0 {domain} # {timestamp} | {score_breakdown} | Ly do: {reason_str}\n"

                            with open(self.suspect_file, "a", encoding="utf-8") as f:
                                f.write(log_entry)

                            self.log(f"[BOT-{bot_id} NGHI NGO] {domain} | {score_breakdown} | {reason_str}")

                # 3. Duoi 40 diem: Trang an toan hoac khong du dau hieu ket luan (bo qua)

                # Dao sau link thu hoach duoc
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
        self.log(f"Khoi dong he thong voi {self.max_workers} bot phan loai da tin hieu (Bang trong so 100d + Co che tru diem)...")
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
                self.log(f"[Trang thai] Dang chay {self.max_workers} bot song song | Hang doi: {self.url_queue.qsize()} URL | Tong domain da xu ly: {len(self.seen_domains)}")
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
