#!/usr/bin/env python3
"""配置 GitHub Actions Secrets.

用法: python3 scripts/setup_github_secrets.py
"""
from __future__ import annotations

import json
import sys
from base64 import b64decode, b64encode

import requests
from nacl import encoding, public

# 配置（从环境变量读取，避免敏感信息泄露）
import os
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPO", "wangdan197902-art/ai-pricing")

SECRETS = {
    "NETLIFY_AUTH_TOKEN": os.environ.get("NETLIFY_AUTH_TOKEN", ""),
    "NETLIFY_SITE_ID": os.environ.get("NETLIFY_SITE_ID", ""),
    "AGNES_LLM_API_KEY": os.environ.get("AGNES_LLM_API_KEY", ""),
    "AGNES_LLM_BASE_URL": os.environ.get("AGNES_LLM_BASE_URL", "https://apihub.agnes-ai.com/v1"),
    "AGNES_LLM_MODEL": os.environ.get("AGNES_LLM_MODEL", "agnes-2.0-flash"),
}

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get_repo_public_key() -> tuple[str, str]:
    """获取仓库公钥用于加密 secrets."""
    url = f"https://api.github.com/repos/{REPO}/actions/secrets/public-key"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["key_id"], data["key"]


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """用仓库公钥加密 secret value."""
    public_key_raw = b64decode(public_key_b64)
    public_key = public.PublicKey(public_key_raw)
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")


def put_secret(key_id: str, public_key: str, name: str, value: str) -> bool:
    """PUT 一个 secret 到 GitHub."""
    encrypted_value = encrypt_secret(public_key, value)
    url = f"https://api.github.com/repos/{REPO}/actions/secrets/{name}"
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id,
    }
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code in (201, 204):
        return True
    print(f"  ❌ 失败: {resp.status_code} {resp.text[:200]}")
    return False


def main() -> int:
    print(f"=== 配置 GitHub Secrets for {REPO} ===\n")
    try:
        key_id, public_key = get_repo_public_key()
        print(f"✅ 获取仓库公钥成功 (key_id: {key_id[:8]}...)\n")
    except Exception as exc:
        print(f"❌ 获取仓库公钥失败: {exc}")
        return 1

    success_count = 0
    for name, value in SECRETS.items():
        print(f"[{success_count + 1}/{len(SECRETS)}] 配置 {name}...", end=" ")
        if put_secret(key_id, public_key, name, value):
            print("✅")
            success_count += 1
        else:
            print("❌")

    print(f"\n=== 完成 ===")
    print(f"成功: {success_count}/{len(SECRETS)}")
    return 0 if success_count == len(SECRETS) else 1


if __name__ == "__main__":
    sys.exit(main())
