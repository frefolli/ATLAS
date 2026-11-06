"""Push of main and of all the tags to GitHub via SSH (dulwich), without force: an existing history is not overwritten.
  python scripts/github_push.py <private key file>      (with PYTHONPATH=src; see scripts/PUBBLICAZIONE.md)"""
import sys
from pathlib import Path

import dulwich.client
from dulwich import porcelain
from dulwich.repo import Repo

from arcadia_tool.storage.repository import _WindowlessSSHVendor

URL = "git@github.com:salvodesi/ATLAS.git"

key = sys.argv[1]
repo = Repo(str(Path(__file__).resolve().parents[1]))
refs = [b"refs/heads/main"] + sorted(r for r in repo.refs.keys() if r.startswith(b"refs/tags/"))
dulwich.client.get_ssh_vendor = _WindowlessSSHVendor
porcelain.push(repo, URL, [r + b":" + r for r in refs], key_filename=key)
for r in refs:
    print(r.decode(), "->", repo.refs[r].decode()[:8])
