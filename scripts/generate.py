#!/usr/bin/env python3
"""Builds the static Terraform provider registry served at registry.proxcenter.io.

It implements the provider registry protocol
(https://developer.hashicorp.com/terraform/internals/provider-registry-protocol)
as plain JSON files under public/. The provider binaries are not copied: each
download document points at the signed assets of the GitHub release.

Usage: python3 scripts/generate.py [output_dir]   (default: public)
Reads the public GitHub releases of each provider listed in PROVIDERS; set
GITHUB_TOKEN to raise the API rate limit.
"""
import json
import os
import pathlib
import re
import sys
import urllib.request

NAMESPACE = "adminsyspro"
# provider type -> GitHub repository holding its releases
PROVIDERS = {"proxcenter": "adminsyspro/terraform-provider-proxcenter"}
KEY_FILE = pathlib.Path(__file__).with_name("proxcenter-provider-signing-key.asc")
KEY_ID = "E6F5F38BE03A888F"
ASSET_RE = re.compile(r"^terraform-provider-(?P<type>[a-z0-9-]+)_(?P<version>[0-9][^_]*)_(?P<os>[a-z0-9]+)_(?P<arch>[a-z0-9]+)\.zip$")


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "proxcenter-registry-generator"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def releases(repo):
    out, page = [], 1
    while True:
        batch = json.loads(get(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"))
        if not batch:
            return out
        out += [r for r in batch if not r["draft"] and not r["prerelease"]]
        page += 1


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def build(out):
    armor = KEY_FILE.read_text()
    write(out / ".well-known" / "terraform.json", {"providers.v1": "/v1/providers/"})
    for ptype, repo in PROVIDERS.items():
        base = out / "v1" / "providers" / NAMESPACE / ptype
        versions = []
        for rel in releases(repo):
            assets = {a["name"]: a["browser_download_url"] for a in rel["assets"]}
            version = rel["tag_name"].lstrip("v")
            sums_name = f"terraform-provider-{ptype}_{version}_SHA256SUMS"
            if sums_name not in assets or sums_name + ".sig" not in assets:
                print(f"skip {rel['tag_name']}: no signed SHA256SUMS", file=sys.stderr)
                continue
            shasums = {}
            for line in get(assets[sums_name]).decode().splitlines():
                digest, _, name = line.partition("  ")
                shasums[name.strip()] = digest
            platforms = []
            for name, url in sorted(assets.items()):
                m = ASSET_RE.match(name)
                if not m or m["type"] != ptype or m["version"] != version:
                    continue
                platforms.append({"os": m["os"], "arch": m["arch"]})
                write(base / version / "download" / m["os"] / m["arch"], {
                    "protocols": ["6.0"],
                    "os": m["os"],
                    "arch": m["arch"],
                    "filename": name,
                    "download_url": url,
                    "shasums_url": assets[sums_name],
                    "shasums_signature_url": assets[sums_name + ".sig"],
                    "shasum": shasums[name],
                    "signing_keys": {"gpg_public_keys": [{
                        "key_id": KEY_ID,
                        "ascii_armor": armor,
                        "trust_signature": "",
                        "source": "ProxCenter",
                        "source_url": "https://registry.proxcenter.io/",
                    }]},
                })
            versions.append({"version": version, "protocols": ["6.0"], "platforms": platforms})
        write(base / "versions", {"versions": versions})
        print(f"{NAMESPACE}/{ptype}: {', '.join(v['version'] for v in versions)}")


if __name__ == "__main__":
    build(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "public"))
