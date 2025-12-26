#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/siteverification",
]

DOMAINS_FILE  = "domain.txt"
CLIENT_SECRET = "client_secret.json"
TOKEN_STORE   = "token.json"
TOKENS_DIR    = Path("tokens")

def build_creds():
    # WAJIB: token.json harus sudah dibuat dari login lokal pertama
    if not os.path.exists(TOKEN_STORE):
        print("[!] token.json tidak ditemukan.")
        print(">>> Jalankan sekali di lokal: python bulk.py agar token.json terbentuk")
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(TOKEN_STORE, SCOPES)

    # refresh otomatis jika expired
    if creds.expired and creds.refresh_token:
        print("[i] Token expired → refresh..")
        creds.refresh(Request())
        Path(TOKEN_STORE).write_text(creds.to_json(), encoding="utf-8")

    return creds

def norm_url(s: str) -> str:
    s = s.strip()
    if not s: return ""
    if not re.match(r"^https?://", s, flags=re.I):
        s = "https://" + s
    return s.rstrip("/") + "/"

def read_sites():
    with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            u = norm_url(line)
            if u: yield u

if __name__ == "__main__":
    if not os.path.exists(DOMAINS_FILE): sys.exit(f"[!] {DOMAINS_FILE} tidak ditemukan.")
    if not os.path.exists(CLIENT_SECRET): sys.exit(f"[!] {CLIENT_SECRET} tidak ditemukan.")
    TOKENS_DIR.mkdir(exist_ok=True)

    creds = build_creds()
    gsc = build("searchconsole", "v1", credentials=creds)
    sv  = build("siteVerification", "v1", credentials=creds)

    sites = list(read_sites())
    if not sites: sys.exit("[!] domain.txt kosong.")

    print(f"[i] Total sites: {len(sites)}")

    for site in sites:
        print(f"\n=== {site} ===")

        # 1) Tambahkan property
        try:
            gsc.sites().add(siteUrl=site).execute()
            print(f"[+] Property added: {site}")
        except Exception as e:
            print(f"[!] Add failed: {e}")

        # 2) Ambil token verification file
        try:
            body = {"site": {"type": "SITE", "identifier": site}, "verificationMethod": "FILE"}
            token = sv.webResource().getToken(body=body).execute()["token"]
            file_url = urljoin(site, token)

            (TOKENS_DIR / token).write_text(f"google-site-verification: {token}\n", encoding="utf-8")
            print(f"[i] File verification: {token}")
            print(f"    Upload file ke: {file_url}")
        except Exception as e:
            print(f"[!] getToken failed: {e}")
            continue

        # 3) Coba verifikasi langsung
        try:
            resp = sv.webResource().insert(
                verificationMethod="FILE",
                body={"verificationMethod": "FILE", "site": {"type": "SITE", "identifier": site}},
            ).execute()

            owners = ", ".join(resp.get("owners", [])) or "-"
            print(f"[✓] VERIFIED: {site} | Owners: {owners}")

        except Exception as e:
            print(f"[x] Verify failed: {e}")

            try:
                r = requests.get(file_url, timeout=10)
                print(f"    [hint] HTTP={r.status_code}, size={len(r.text)}")
            except:
                print("    [hint] File tidak dapat diakses")

    print("\n✔ DONE tanpa laporan CSV.")
