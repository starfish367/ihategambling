#!/usr/bin/env python3
"""
gambling-crawler.py - Bot tu dong cao search engine, phan tich noi dung va gom domain ca do
Ho tro:
- Da luong (> 10 bot chay song song)
- Chay lien tuc (Continuous discovery loop)
- Dao tim lien ket ngam (Recursive link harvesting tu cac trang da phat hien)
- Nhan dien pattern ten mien co bac (Tieng Anh + 88, 77, 68, 79, 388, 789...)
- Bo tu dien ca do / tai xiu / nha cai mo rong toan dien
- Xoay vong Free Proxy tu dong
- Xuat danh sach chan vao suspicious_domains.txt
"""

import sys
import os
import re
import time
import random
import threading
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

# Danh sach tien to thuong hieu ca do, nha cai, cong game pho bien nhat
BRAND_PREFIXES = [
    # Nha cai the thao / Casino
    "bet", "win", "club", "casino", "vip", "ku", "th", "sh", "fb", "fun",
    "f8", "ok", "new", "jun", "hi", "bk", "w", "m", "789", "b52", "rik", "sun",
    "go", "iwin", "hit", "taixiu", "nohu", "top", "king", "soc", "vic", "rio",
    "zowin", "macau", "sin", "de", "z", "ox", "five", "red", "sky", "ta",
    "lucky", "da", "lode", "mu", "fc", "nbet", "bong", "sbo", "saba", "cmd",
    "k9", "vg", "v8", "v9", "fa", "yo", "may", "gem", "bay", "boc"
]

# Cac con so may man / nhan dien dac trung thuong gan sau thuong hieu
BRAND_NUMBERS = [
    "88", "77", "99", "68", "79", "388", "888", "999", "789", "52", "188",
    "66", "365", "123", "247", "11", "22", "33", "86", "6868", "8888", "9999"
]

# Pattern ten mien co bac dac trung (Tu tieng Anh + cac con so 88, 77, 68, 79...)
GAMBLING_DOMAIN_PATTERN = re.compile(
    r"([a-z0-9\-]+(?:88|77|99|68|79|388|888|789|999|52|188|365|6868|8888)[a-z0-9\-]*\.[a-z]{2,})",
    re.IGNORECASE
)

# Danh sach chu de / tu khoa tim kiem mo rong tren Search Engine
BASE_SEARCH_TERMS = [
    # Tai xiu & Game bai
    "tài xỉu online", "tài xỉu md5 uy tín", "tải game tài xỉu đổi thưởng", "game bài đổi thưởng nạp rút 1-1",
    "xóc đĩa trực tuyến", "bầu cua tôm cá online", "bắn cá nổ hũ đổi tiền thật", "quay hũ jackpot",
    # Live Casino & Baccarat
    "baccarat trực tuyến", "kéo baccarat về bờ", "nhóm hô baccarat tele", "sòng bạc casino trực tuyến",
    "live baccarat tặng tiền", "roulette trực tuyến uy tín", "rồng hổ online",
    # The thao & Keo nha cai
    "kèo nhà cái hôm nay", "tỷ lệ kèo bóng đá trực tuyến", "kèo chấp châu á hôm nay", "kèo tài xỉu bóng đá",
    "cá cược bóng đá euro world cup", "soi kèo ngoại hạng anh đêm nay", "kèo phạt góc running",
    # Da ga & Lo de
    "đá gà thomo trực tiếp hôm nay", "đá gà cpc3 trực tiếp", "trực tiếp đá gà cựa dao c1",
    "lô đề online 1 ăn 99", "đánh số đề miền bắc siêu tốc", "soi cầu lô đề 3 miền vip",
    # Khuyen mai & Link du phong
    "link vào không bị chặn", "nhà cái tặng tiền trải nghiệm", "đăng ký nhận 88k miễn phí",
    "tải app apk ios", "code tân thủ 100k", "nhà cái uy tín nhất việt nam"
]

# Bo tu khoa phan tich chuyen sau trong ma HTML
GAMBLING_INDICATORS = [
    # Tu khoa the loai
    "cá cược", "cá độ", "kèo nhà cái", "tài xỉu", "tài xỉu md5", "baccarat", "casino trực tuyến",
    "đá gà thomo", "đá gà cpc", "đá gà cựa dao", "lô đề online", "bắn cá đổi thưởng", "nổ hũ",
    "game bài đổi thưởng", "xóc đĩa", "bầu cua", "rồng hổ", "sicbo", "roulette",
    # Tu khoa giao dich & khuyen mai
    "nạp rút 1-1", "khuyến mãi tân thủ", "tiền cược miễn phí", "đăng ký nhận 88k", "tặng code tân thủ",
    "tiền cược trải nghiệm", "hoàn trả không giới hạn", "thưởng nạp đầu 100%", "rút tiền 30s",
    # Tu khoa thuong hieu & link vao
    "link vào kubet", "link vào 789bet", "link vào shbet", "nhà cái uy tín", "cược xiên", "kèo châu á",
    "sòng bạc", "live casino", "soi kèo", "game tài xỉu", "sảnh sexy gaming", "sảnh evolution",
    "đại lý cá cược", "tải app apk ios", "link vào không bị chặn"
]

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]

class ContinuousGamblingCrawler:
    def __init__(self, output_file="/home/a/suspicious_domains.txt", max_workers=12, use_proxy=True):
        self.output_file = os.path.abspath(output_file)
        self.max_workers = max_workers
        self.use_proxy = use_proxy
        self.proxies = []
        self.seen_domains = set()
        self.target_queue = set()
        self.lock = threading.Lock()
        self.last_proxy_refresh = 0
        
        # Load domains da luu tu truoc
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

    def fetch_free_proxies(self):
        if not self.use_proxy:
            return
        now = time.time()
        # Cap nhat proxy moi 20 phut mot lan
        if now - self.last_proxy_refresh < 1200 and self.proxies:
            return

        self.log("Dang lam moi danh sach Free Proxy...")
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
        self.log(f"Da nap {len(self.proxies)} free proxy vao bo dem xoay vong.")

    def get_random_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def request_with_retry(self, url, method="GET", data=None, timeout=5, expect_str=None):
        if self.use_proxy and self.proxies:
            for _ in range(2):
                p = random.choice(self.proxies)
                proxy_dict = {"http": f"http://{p}", "https": f"http://{p}"}
                try:
                    headers = self.get_random_headers()
                    if method == "POST":
                        r = requests.post(url, data=data, headers=headers, proxies=proxy_dict, timeout=timeout)
                    else:
                        r = requests.get(url, headers=headers, proxies=proxy_dict, timeout=timeout)
                    if r.status_code == 200:
                        if not expect_str or (expect_str in r.text):
                            return r
                except Exception:
                    pass

        # Fallback truc tiep
        try:
            headers = self.get_random_headers()
            if method == "POST":
                return requests.post(url, data=data, headers=headers, timeout=timeout)
            else:
                return requests.get(url, headers=headers, timeout=timeout)
        except Exception:
            return None

    def search_duckduckgo(self, query):
        self.log(f"Truy van tim kiem: '{query}'")
        r = self.request_with_retry(
            "https://html.duckduckgo.com/html/",
            method="POST",
            data={"q": query},
            timeout=8,
            expect_str="result__url"
        )
        if not r or "result__url" not in r.text:
            return []

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

    def inspect_and_harvest(self, target_url):
        parsed = urlparse(target_url)
        domain = parsed.netloc.lower()
        if not domain or domain in self.seen_domains:
            return

        r = self.request_with_retry(target_url, timeout=6)
        if not r or len(r.text) < 200:
            return

        html_lower = r.text.lower()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # Kiem tra tu khoa noi dung
        matched_kw = [kw for kw in GAMBLING_INDICATORS if kw in html_lower]
        score = len(matched_kw)

        # Kiem tra pattern ten mien co chua so dac trung (88, 77, 68...)
        domain_match = GAMBLING_DOMAIN_PATTERN.search(domain)
        if domain_match:
            score += 3

        # Danh gia co phai trang ca do khong
        is_gambling = (score >= 2) or bool(domain_match and score >= 1) or any(
            kw in title.lower() for kw in ["nhà cái", "cá cược", "tài xỉu", "casino", "baccarat", "xóc đĩa", "đá gà"]
        )

        if is_gambling:
            with self.lock:
                if domain not in self.seen_domains:
                    self.seen_domains.add(domain)
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    reason = []
                    if domain_match:
                        reason.append(f"Domain Pattern '{domain_match.group(1)}'")
                    if matched_kw:
                        reason.append(f"Tu khoa: {', '.join(matched_kw[:3])}")
                    reason_str = " | ".join(reason) if reason else "Dau hieu xac thuc"

                    log_entry = f"0.0.0.0 {domain} # {timestamp} | Diem: {score} | {reason_str}\n"
                    with open(self.output_file, "a", encoding="utf-8") as f:
                        f.write(log_entry)
                    self.log(f"[PHAT HIEN] {domain} (Diem: {score}, Title: {title[:30]}...)")

            # Dao sau (Harvest): Trich xuat them cac link ngoai tu trang ca do nay de dua vao hang doi
            for a_tag in soup.find_all("a", href=True):
                link = a_tag["href"].strip()
                if link.startswith("http"):
                    link_dom = urlparse(link).netloc.lower()
                    if link_dom and link_dom not in self.seen_domains:
                        with self.lock:
                            if len(self.target_queue) < 1000:
                                self.target_queue.add(link)

    def generate_dynamic_query(self):
        """Sinh tu khoa tim kiem ngau nhien ket hop ten tieng Anh va con so (88, 77, ...)"""
        brand = random.choice(BRAND_PREFIXES) + random.choice(BRAND_NUMBERS)
        base = random.choice(BASE_SEARCH_TERMS)
        variations = [
            f"{base} {brand}",
            f"link vào {brand}",
            f"nhà cái {brand}",
            f"{brand} casino trực tuyến",
            f"tải app {brand} tài xỉu",
            f"đăng ký {brand} nhận code",
            f"soi kèo {brand}",
            f"đá gà {brand} trực tiếp",
            f"game bài {brand} đổi thưởng"
        ]
        return random.choice(variations)

    def run_continuous(self):
        self.log(f"Khoi dong {self.max_workers} bot chay cao du lieu lien tuc...")
        self.fetch_free_proxies()

        loop_count = 0
        while True:
            loop_count += 1
            self.fetch_free_proxies()

            # 1. Thu thap link tu search engine bang tu khoa sinh tu dong
            query = self.generate_dynamic_query()
            search_links = self.search_duckduckgo(query)
            
            with self.lock:
                for lk in search_links:
                    self.target_queue.add(lk)

            # 2. Lay danh sach URL tu hang doi de xu ly
            current_batch = []
            with self.lock:
                while self.target_queue and len(current_batch) < 30:
                    current_batch.append(self.target_queue.pop())

            if current_batch:
                self.log(f"[Vong {loop_count}] Dang quet song song {len(current_batch)} trang web (Hang doi con: {len(self.target_queue)})...")
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    executor.map(self.inspect_and_harvest, current_batch)

            self.log(f"Tong so ten mien ca do da luu: {len(self.seen_domains)}")
            time.sleep(random.uniform(2.0, 4.0))


def main():
    args = sys.argv[1:]
    output_path = "/home/a/suspicious_domains.txt"
    threads = 12
    use_proxy = True

    if "--output" in args:
        idx = args.index("--output")
        if len(args) > idx + 1:
            output_path = args[idx + 1]

    if "--threads" in args:
        idx = args.index("--threads")
        if len(args) > idx + 1:
            threads = int(args[idx + 1])

    if "--no-proxy" in args:
        use_proxy = False

    crawler = ContinuousGamblingCrawler(output_file=output_path, max_workers=threads, use_proxy=use_proxy)
    crawler.run_continuous()


if __name__ == "__main__":
    main()
