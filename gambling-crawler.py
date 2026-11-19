#!/usr/bin/env python3
"""
gambling-crawler.py - He thong Crawler da luong chay lien tuc (Producer-Consumer Pipeline)
Ho tro:
- Chay dong thoi 15-20+ bot khong ngung nghi (Khong bao gio dung/treo)
- Tuyen Search Engine Harvester bom URL lien tuc vao hang doi
- Chuyen sau: Co bac, Tai xiu (chu tieng Anh + so 88, 77...) & Lua dao Campuchia (bay viec lam, giat don)
- Whitelist tuyet doi (Khong bao gio bat nham Youtube, Google, bao chi chinh thong)
- Tieu chi cham diem nghiem ngat (Diem >= 3)
- Tu dong xoay vong Free Proxy
"""

import sys
import os
import re
import time
import random
import queue
import threading
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

# Danh sach tien to thuong hieu ca do, nha cai, cong game
BRAND_PREFIXES = [
    "bet", "win", "club", "casino", "vip", "ku", "th", "sh", "fb", "fun",
    "f8", "ok", "new", "jun", "hi", "bk", "w", "m", "789", "b52", "rik", "sun",
    "go", "iwin", "hit", "taixiu", "nohu", "top", "king", "soc", "vic", "zowin",
    "macau", "sin", "debet", "oxbet", "five", "red", "sky", "ta88", "lucky",
    "bong", "sbo", "saba", "cmd", "k9", "vg", "v8", "v9", "fa88", "yo88"
]

# Cac con so may man dac trung gan sau thuong hieu
BRAND_NUMBERS = [
    "88", "77", "99", "68", "79", "388", "888", "999", "789", "52", "188",
    "66", "365", "123", "247", "86", "6868", "8888", "9999"
]

# Pattern ten mien co bac (chu tieng Anh + so 88, 77, 68...)
GAMBLING_DOMAIN_PATTERN = re.compile(
    r"([a-z0-9\-]+(?:88|77|99|68|79|388|888|789|999|52|188|365|6868|8888)[a-z0-9\-]*\.[a-z]{2,})",
    re.IGNORECASE
)

# Danh sach tu khoa tim kiem luu luong cao (Luon tra ve ket qua phong phu tren search engine)
HIGH_YIELD_SEARCH_QUERIES = [
    # Co bac, Tai xiu & Game bai
    "tài xỉu online uy tín", "tải game tài xỉu đổi thưởng", "tài xỉu md5 nạp rút",
    "game bài đổi thưởng uy tín", "kèo nhà cái hôm nay trực tiếp", "tỷ lệ kèo bóng đá trực tuyến",
    "baccarat trực tuyến uy tín", "kéo baccarat về bờ", "live casino trực tuyến",
    "đá gà thomo trực tiếp hôm nay", "đá gà cpc3 cpc4", "lô đề online 1 ăn 99",
    "nhà cái tặng tiền trải nghiệm", "link vào không bị chặn mới nhất",
    "nổ hũ jackpot đổi tiền", "bắn cá đổi thưởng 2026", "xóc đĩa trực tuyến nạp rút 1-1",
    # Lua dao Campuchia & Bay viec lam
    "tuyển dụng việc làm campuchia lương cao", "tuyển dụng casino bavet", "việc nhẹ lương cao mộc bài",
    "tuyển cskh campuchia bao ăn ở", "tuyển telesale campuchia lương 30 triệu",
    "tuyển dụng casino sihanoukville", "việc làm casino chrey thum",
    # Lua dao nhiem vu / Giat don
    "làm nhiệm vụ telegram nhận hoa hồng", "app giật đơn kiếm tiền nạp tiền",
    "đầu tư tài chính sinh lời mỗi ngày cam kết", "tuyển cộng tác viên nhiệm vụ shopee tiki"
]

# Bo tu khoa phan tich trong noi dung HTML
GAMBLING_AND_SCAM_KEYWORDS = [
    # Co bac & Tai xiu
    "cá cược", "cá độ", "kèo nhà cái", "tài xỉu", "tài xỉu md5", "baccarat", "casino trực tuyến",
    "đá gà thomo", "đá gà cpc", "lô đề online", "bắn cá đổi thưởng", "nổ hũ", "game bài đổi thưởng",
    "xóc đĩa", "bầu cua", "rồng hổ", "nạp rút 1-1", "tiền cược miễn phí", "đăng ký nhận 88k",
    "link vào kubet", "link vào 789bet", "link vào shbet", "nhà cái uy tín", "kèo châu á",
    "live casino", "soi kèo", "game tài xỉu",
    # Lua dao Campuchia & Bay viec lam
    "việc làm campuchia", "việc nhẹ lương cao", "casino bavet", "casino chrey thum", "sihanoukville",
    "mộc bài tây ninh", "tuyển cskh campuchia", "tuyển telesale campuchia", "bao ăn ở campuchia",
    "xuất cảnh campuchia", "lương 20-30 triệu", "biết gõ máy tính",
    # Lua dao nhiem vu & Giat don
    "làm nhiệm vụ nhận hoa hồng", "giật đơn nhận tiền", "nạp tiền làm nhiệm vụ", "nhiệm vụ shopee",
    "hoàn tiền nhiệm vụ", "đầu tư sinh lời mỗi ngày", "sàn chứng khoán quốc tế ảo"
]

# WHITELIST TUYET DOI - Khong bao gio danh dau cac domain nay
WHITELIST_DOMAINS = {
    "youtube.com", "youtu.be", "googlevideo.com", "google.com", "google.com.vn",
    "facebook.com", "fb.com", "messenger.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "github.com", "gitlab.com", "wikipedia.org",
    "apple.com", "microsoft.com", "cloudflare.com", "zalo.me", "tiki.vn",
    "shopee.vn", "lazada.vn", "bluestacks.com", "apkpure.com",
    # Bao chi & truyen thong chinh thong
    "vnexpress.net", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn", "24h.com.vn",
    "kenh14.vn", "zingnews.vn", "znews.vn", "baomoi.com", "vtv.vn", "vietnamnet.vn"
}

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]

class HighThroughputCrawler:
    def __init__(self, output_file="/home/a/suspicious_domains.txt", max_workers=16, use_proxy=True):
        self.output_file = os.path.abspath(output_file)
        self.max_workers = max_workers
        self.use_proxy = use_proxy
        self.proxies = []
        self.seen_domains = set()
        self.url_queue = queue.Queue(maxsize=5000)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_proxy_refresh = 0

        # Load danh sach domain da luu
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
        if now - self.last_proxy_refresh < 1200 and self.proxies:
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
        self.log(f"Da nap {len(self.proxies)} free proxy vao bo dem.")

    def get_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def request_get(self, url, timeout=6):
        if self.use_proxy and self.proxies:
            for _ in range(2):
                p = random.choice(self.proxies)
                try:
                    r = requests.get(url, headers=self.get_headers(), proxies={"http": f"http://{p}", "https": f"http://{p}"}, timeout=timeout)
                    if r.status_code == 200:
                        return r
                except Exception:
                    pass
        # Fallback ket noi truc tiep
        try:
            return requests.get(url, headers=self.get_headers(), timeout=timeout)
        except Exception:
            return None

    def search_duckduckgo(self, query):
        url = "https://html.duckduckgo.com/html/"
        headers = self.get_headers()
        try:
            r = requests.post(url, data={"q": query}, headers=headers, timeout=8)
            if r.status_code == 200 and "result__url" in r.text:
                soup = BeautifulSoup(r.text, "html.parser")
                results = []
                for a in soup.find_all("a", class_="result__url"):
                    href = a.get("href", "").strip()
                    if "uddg=" in href:
                        qs = parse_qs(urlparse(href).query)
                        if "uddg" in qs:
                            href = qs["uddg"][0]
                    if href.startswith("http"):
                        results.append(href)
                return results
        except Exception:
            pass
        return []

    def producer_thread(self):
        """Tuyen tim kiem lien tuc de bom URL vao hang doi (Producer)"""
        self.log("Khoi dong luong tim kiem Search Engine (Producer)...")
        query_pool = list(HIGH_YIELD_SEARCH_QUERIES)
        random.shuffle(query_pool)
        idx = 0

        while not self.stop_event.is_set():
            # Neu hang doi URL con duoi 150 link thi lap tuc tim kiem tiep
            if self.url_queue.qsize() < 150:
                if idx >= len(query_pool):
                    # Sinh them tu khoa ket hop brand + so
                    brand = random.choice(BRAND_PREFIXES) + random.choice(BRAND_NUMBERS)
                    q = f"link vào {brand} tài xỉu uy tín"
                else:
                    q = query_pool[idx]
                    idx += 1

                self.log(f"[Search Engine] Dang quet: '{q}' (Hang doi hien tai: {self.url_queue.qsize()} URL)")
                links = self.search_duckduckgo(q)
                added = 0
                for lk in links:
                    dom = urlparse(lk).netloc.lower()
                    if dom and not self.is_whitelisted(dom) and dom not in self.seen_domains:
                        try:
                            self.url_queue.put_nowait(lk)
                            added += 1
                        except queue.Full:
                            break
                if added > 0:
                    self.log(f"  -> Nap them {added} URL moi vao hang doi xu ly.")
                time.sleep(random.uniform(2.0, 3.5))
            else:
                time.sleep(3.0)

    def worker_thread(self, bot_id):
        """Luong xu ly URL: Cao noi dung, kiem tra co bac/lua dao va dao link (Consumer)"""
        while not self.stop_event.is_set():
            try:
                target_url = self.url_queue.get(timeout=2.0)
            except queue.Empty:
                continue

            try:
                parsed = urlparse(target_url)
                domain = parsed.netloc.lower()
                if not domain or self.is_whitelisted(domain) or domain in self.seen_domains:
                    self.url_queue.task_done()
                    continue

                r = self.request_get(target_url, timeout=6)
                if not r or len(r.text) < 200:
                    self.url_queue.task_done()
                    continue

                html_lower = r.text.lower()
                soup = BeautifulSoup(r.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""

                # Cham diem tu khoa
                matched = [kw for kw in GAMBLING_AND_SCAM_KEYWORDS if kw in html_lower]
                score = len(matched)

                # So khop pattern ten mien co bac (chu + so 88, 77...)
                domain_match = GAMBLING_DOMAIN_PATTERN.search(domain)
                if domain_match:
                    score += 3

                # DIEU KIEN XAC THUC NGHIEM NGAT:
                # - Diem tu khoa >= 3
                # - Hoac co Pattern domain + diem >= 2
                # - Hoac tieu de chua ro rang tu khoa ca do/lua dao + diem >= 2
                is_scam = (
                    (score >= 3) or
                    (domain_match and score >= 2) or
                    (any(kw in title.lower() for kw in ["nhà cái", "tài xỉu", "casino", "baccarat", "kèo nhà cái", "việc làm campuchia", "bavet"]) and score >= 2)
                )

                if is_scam and not self.is_whitelisted(domain):
                    with self.lock:
                        if domain not in self.seen_domains:
                            self.seen_domains.add(domain)
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            reason = []
                            if domain_match:
                                reason.append(f"Pattern '{domain_match.group(1)}'")
                            if matched:
                                reason.append(f"Tu khoa: {', '.join(matched[:3])}")
                            log_entry = f"0.0.0.0 {domain} # {timestamp} | Diem: {score} | {' | '.join(reason)}\n"
                            with open(self.output_file, "a", encoding="utf-8") as f:
                                f.write(log_entry)
                            self.log(f"[BOT-{bot_id} PHAT HIEN] {domain} (Diem: {score}, Title: {title[:28]}...)")

                    # Dao sau (Harvest): lay link ngoai nhét vao hang doi tiep tuc quet
                    for a_tag in soup.find_all("a", href=True):
                        link = a_tag["href"].strip()
                        if link.startswith("http"):
                            link_dom = urlparse(link).netloc.lower()
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
        self.log(f"Khoi dong he thong voi {self.max_workers} bot xu ly dong thoi (Producer-Consumer)...")
        self.fetch_free_proxies()

        # Khoi dong 1 luong Producer
        prod = threading.Thread(target=self.producer_thread, daemon=True)
        prod.start()

        # Khoi dong N luong Consumer (cac bot cào noi dung)
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
                self.log(f"[Trang thai] Dang chay {self.max_workers} bot song song | Hang doi: {self.url_queue.qsize()} URL | Tong domain da tóm: {len(self.seen_domains)}")
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

    crawler = HighThroughputCrawler(output_file=output_path, max_workers=threads, use_proxy=use_proxy)
    crawler.run(max_minutes=minutes)


if __name__ == "__main__":
    main()
