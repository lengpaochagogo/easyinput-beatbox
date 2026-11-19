import base64
import json
import os
import sys
import urllib.request

TOKEN = os.environ["GH_TOKEN"]
REPO = "lengpaochagogo/easyinput-beatbox"
API = f"https://api.github.com/repos/{REPO}"
ROOT = os.path.dirname(os.path.abspath(__file__))


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read().decode()
    return json.loads(body) if body else {}


def collect(repo_dir):
    """收集所有文件 -> git tree 格式"""
    entries = []
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "build", "dist")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, repo_dir).replace(os.sep, "/")
            if rel.startswith(".git/"):
                continue
            with open(full, "rb") as f:
                raw = f.read()
            mode = "100755" if os.access(full, os.X_OK) else "100644"
            entries.append({
                "path": rel,
                "mode": mode,
                "type": "blob",
                "sha": None,
                "_raw": raw,
            })
    return entries


def main():
    entries = collect(ROOT)
    print(f"收集到 {len(entries)} 个文件")

    # 1. 创建 blobs
    for i, e in enumerate(entries, 1):
        e["sha"] = api("POST", "/git/blobs",
                       {"content": base64.b64encode(e.pop("_raw")).decode(),
                        "encoding": "base64"})["sha"]
        if i % 20 == 0:
            print(f"  blobs {i}/{len(entries)}")

    # 2. 创建 tree
    tree = api("POST", "/git/trees",
               {"base_tree": None, "tree": [
                   {"path": e["path"], "mode": e["mode"], "type": "blob", "sha": e["sha"]}
                   for e in entries]})
    print(f"tree SHA: {tree['sha']}  (truncated={tree.get('truncated')})")

    # 3. 创建 commit
    commit = api("POST", "/git/commits", {
        "message": "Initial commit: EasyInput Beatbox (ESP32-S3 drum machine)\n\n"
                   "复刻自 Zhaohan-Wang/easyinput-beatbox (MIT License)\n"
                   "板端负责走拍与实时发声，电脑端负责可视化与 Pattern 编辑。",
        "tree": tree["sha"],
        "parents": [],
    })
    print(f"commit SHA: {commit['sha']}")

    # 4. 更新 main 分支
    try:
        api("PATCH", "/git/refs/heads/main", {"sha": commit["sha"], "force": True})
    except Exception:
        api("POST", "/git/refs", {"ref": "refs/heads/main", "sha": commit["sha"]})
    print("✅ 分支 main 已更新")


if __name__ == "__main__":
    main()
