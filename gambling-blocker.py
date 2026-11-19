#!/usr/bin/env python3
"""
gambling-blocker.py - Bot thu thap va chan ten mien ca do, co bac cho he thong Linux / Armbian
Hoan toan dung thu vien chuan Python 3 (khong can pip, tieu thu < 30MB RAM).
"""

import sys
import os
import re
import ssl
import socket
import urllib.request
import urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Danh sach feed blacklist co bac / ca do duoc cap nhat lien tuc tu cong dong
COMMUNITY_FEEDS = [
    # StevenBlack Gambling list
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling-only/hosts",
    # HaGeZi Gambling Blocklist (onlydomains)
    "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/gambling-onlydomains.txt"
]

# Bo tu khoa nhan dien trang web ca do, co bac (tieng Viet & quoc te)
GAMBLING_KEYWORDS = [
    "cá cược", "cá độ", "kèo nhà cái", "tài xỉu", "baccarat", "casino trực tuyến",
    "đá gà thomo", "lô đề online", "bắn cá đổi thưởng", "nổ hũ", "game bài đổi thưởng",
    "link vào kubet", "link vào 789bet", "nhà cái uy tín", "nạp rút 1-1", "khuyến mãi tân thủ",
    "online casino", "sports betting", "slot games", "live baccarat", "roulette"
]

OUTPUT_HOSTS_FILE = os.path.expanduser("~/gambling_hosts.txt")
SYSTEM_HOSTS_FILE = "/etc/hosts"
TAG_START = "# --- GAMBLING_BLOCKER_START ---"
TAG_END   = "# --- GAMBLING_BLOCKER_END ---"

# Bo qua kiem tra chung chi SSL nghiem ngat khi bot crawl cac web la
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_domain(raw_line):
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    # Xoa 0.0.0.0 hoac 127.0.0.1 neu co o dau dong
    line = re.sub(r"^(0\.0\.0\.0|127\.0\.0\.1)\s+", "", line)
    # Xoa comment phia sau
    line = line.split("#")[0].strip()
    # Kiem tra dinh dang ten mien hop le
    if re.match(r"^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", line):
        return line.lower()
    return None

def fetch_feed(url):
    domains = set()
    print(f"[*] Dang tai du lieu tu: {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as response:
            content = response.read().decode("utf-8", errors="ignore")
            for line in content.splitlines():
                dom = clean_domain(line)
                if dom:
                    domains.add(dom)
        print(f"    -> Lay thanh cong {len(domains)} ten mien.")
    except Exception as e:
        print(f"    [!] Loi khi tai feed: {e}")
    return domains

def check_gambling_content(url):
    """
    Bot cao noi dung HTML va cham diem tu khoa de xac dinh co phai trang ca do khong.
    Tra ve: (is_gambling, domain, score, matched_keywords)
    """
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            html = resp.read().decode("utf-8", errors="ignore").lower()
            matched = [kw for kw in GAMBLING_KEYWORDS if kw in html]
            score = len(matched)
            is_gambling = score >= 2  # Trung khop tu 2 tu khoa dac trung tro len
            return is_gambling, domain, score, matched
    except Exception as e:
        return False, domain, 0, []

def update_system_hosts(domain_list):
    """
    Ghi danh sach ten mien vao /etc/hosts duoi dang 0.0.0.0 domain
    """
    print(f"[*] Dang cap nhat {len(domain_list)} ten mien vao {SYSTEM_HOSTS_FILE}...")
    block_lines = [TAG_START + "\n"]
    for dom in sorted(domain_list):
        block_lines.append(f"0.0.0.0 {dom}\n")
    block_lines.append(TAG_END + "\n")
    block_text = "".join(block_lines)

    try:
        current_content = ""
        if os.path.exists(SYSTEM_HOSTS_FILE):
            with open(SYSTEM_HOSTS_FILE, "r", encoding="utf-8") as f:
                current_content = f.read()

        # Loai bo block cu neu da ton tai
        if TAG_START in current_content and TAG_END in current_content:
            pattern = re.compile(rf"{re.escape(TAG_START)}.*?{re.escape(TAG_END)}\n?", re.DOTALL)
            new_content = pattern.sub("", current_content)
        else:
            new_content = current_content

        if not new_content.endswith("\n"):
            new_content += "\n"
        new_content += block_text

        # Ghi vao tep tam roi dung sudo cp hoac ghi truc tiep neu co quyen
        temp_file = "/tmp/new_hosts.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        res = os.system(f"echo a | sudo -S cp {temp_file} {SYSTEM_HOSTS_FILE} && rm -f {temp_file}")
        if res == 0:
            print("[+] Da chan thanh cong trong /etc/hosts! Tat ca trinh duyet va ung dung se khong the truy cap.")
        else:
            print(f"[!] Can quyen root de sua {SYSTEM_HOSTS_FILE}. Vui long chay voi sudo.")
    except Exception as e:
        print(f"[!] Loi khi cap nhat hosts: {e}")

def main():
    args = sys.argv[1:]
    
    if "--scan" in args:
        # Che do bot kiem tra mot hoac nhieu trang web cu the
        idx = args.index("--scan")
        target_urls = args[idx+1:] if len(args) > idx+1 else []
        if not target_urls:
            print("Cach dung: python3 gambling-blocker.py --scan <url1> [url2] ...")
            return
        
        print(f"[*] Bot dang quet va phan tich {len(target_urls)} trang web...")
        for url in target_urls:
            is_g, dom, score, kw = check_gambling_content(url)
            if is_g:
                print(f"[CANH BAO] {dom} LA TRANG CA DO/CO BAC! (Diem: {score}, Tu khoa: {', '.join(kw)})")
            else:
                print(f"[AN TOAN] {dom} khong phat hien dau hieu ca do.")
        return

    # Che do mac dinh: Thu thap tu feed cong dong + luu danh sach
    print("=== GAMBLING & BETTING BLOCKER BOT (PYTHON) ===")
    all_domains = set()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = executor.map(fetch_feed, COMMUNITY_FEEDS)
        for dom_set in results:
            all_domains.update(dom_set)
            
    print(f"[+] Tong cong thu thap duoc: {len(all_domains)} ten mien ca do doc nhat.")
    
    # Xuat file hosts cuc bo
    with open(OUTPUT_HOSTS_FILE, "w", encoding="utf-8") as f:
        for dom in sorted(all_domains):
            f.write(f"0.0.0.0 {dom}\n")
    print(f"[+] Da xuat danh sach chan ra tep: {OUTPUT_HOSTS_FILE}")

    # Neu co tuy chon --apply thi nap thang vao /etc/hosts
    if "--apply" in args:
        update_system_hosts(all_domains)
    else:
        print("[*] Meo: De ap dung chan truc tiep tren he thong ngay lap tuc, hay chay:")
        print("    python3 gambling-blocker.py --apply")

if __name__ == "__main__":
    main()
