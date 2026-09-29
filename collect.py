"""Collect public TikTok metadata into the existing Social Lens Notion data sources."""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"


def notion(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + os.environ["NOTION_TOKEN"],
                 "Notion-Version": VERSION, "Content-Type": "application/json"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503) or attempt == 4:
                raise RuntimeError(f"Notion HTTP {exc.code}: {exc.read().decode()[:300]}") from exc
            time.sleep(float(exc.headers.get("Retry-After", 2 ** attempt)))


def rich(value):
    return [{"text": {"content": str(value)[:1900]}}]


def existing_pages(source_id, key_property, prefix):
    mapping, cursor = {}, None
    while True:
        body = {"page_size": 100, "filter": {"property": key_property,
                "rich_text": {"starts_with": prefix}}}
        if cursor:
            body["start_cursor"] = cursor
        result = notion("POST", f"/data_sources/{source_id}/query", body)
        for page in result["results"]:
            value = "".join(t.get("plain_text", "") for t in page["properties"][key_property].get("rich_text", []))
            if value:
                mapping[value] = page["id"]
        cursor = result.get("next_cursor")
        if not cursor:
            return mapping


def write(source_id, properties, existing_id=None):
    if existing_id:
        return notion("PATCH", f"/pages/{existing_id}", {"properties": properties})
    return notion("POST", "/pages", {"parent": {"type": "data_source_id",
                  "data_source_id": source_id}, "properties": properties})


def extract(account, limit):
    command = [sys.executable, "-m", "yt_dlp", "--no-download", "--dump-single-json",
               "--playlist-end", str(limit), f"https://www.tiktok.com/@{account}"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=240)
    if result.returncode:
        raise RuntimeError("TikTok extraction failed: " + result.stderr[-800:])
    obj = json.loads(result.stdout)
    return list(obj.get("entries") or [obj])


def metric(item, name):
    value = item.get(name)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse(item, account):
    if not isinstance(item, dict):
        return None
    vid = str(item.get("id") or "")
    if not vid.isdigit():
        return None
    timestamp = item.get("timestamp") or item.get("release_timestamp")
    posted = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date().isoformat() if timestamp else None
    url = f"https://www.tiktok.com/@{account}/video/{vid}"
    title = str(item.get("description") or item.get("title") or f"TikTok {vid}").strip()[:1800]
    metrics = {"Vues": metric(item, "view_count"), "Likes": metric(item, "like_count"),
               "Commentaires": metric(item, "comment_count"), "Partages": metric(item, "repost_count")}
    known = [metrics[f] for f in ("Likes", "Commentaires", "Partages") if metrics[f] is not None]
    metrics["Interactions"] = sum(known) if known else None
    return vid, url, title, posted, metrics


def publication(url, title, posted, metrics, brand):
    props = {"Publication": {"title": rich(title)}, "Clé Social Lens": {"rich_text": rich(url)},
             "Lien": {"url": url}, "Marque": {"rich_text": rich(brand)},
             "Réseau": {"rich_text": rich("TikTok")}, "Format": {"rich_text": rich("Vidéo")},
             "Observation": {"rich_text": rich("Source : données publiques TikTok, extraction yt-dlp")}}
    if posted:
        props["Date"] = {"date": {"start": posted}}
    props.update({field: {"number": value} for field, value in metrics.items() if value is not None})
    return props


def history(account, vid, url, title, metrics, stamp):
    day = stamp[:10]
    key = f"tiktok:{account}:{vid}:{day}"
    props = {"Relevé": {"title": rich(f"@{account} · {title[:100]} · {day}")},
             "Clé relevé": {"rich_text": rich(key)}, "Chaîne": {"rich_text": rich(f"@{account}")},
             "Réseau": {"rich_text": rich("TikTok")}, "Vidéo": {"url": url},
             "Collecté à": {"date": {"start": stamp}}, "Date du relevé": {"date": {"start": day}},
             "Note": {"rich_text": rich("Source : données publiques TikTok ; partages dans Publications")}}
    props.update({field: {"number": metrics[field]} for field in ("Vues", "Likes", "Commentaires", "Interactions")
                  if metrics[field] is not None})
    return key, props


def main():
    pub_source = os.environ["NOTION_PUBLICATIONS_SOURCE_ID"]
    hist_source = os.environ["NOTION_HISTORIQUE_SOURCE_ID"]
    brands = json.loads(os.getenv("TIKTOK_BRANDS_JSON", "{}"))
    accounts = [a.strip().lstrip("@").lower() for a in os.environ["TIKTOK_ACCOUNTS"].split(",") if a.strip()]
    limit = int(os.getenv("MAX_VIDEOS_PER_ACCOUNT", "20"))
    failed = False
    for account in accounts:
        try:
            items = extract(account, limit)
            videos = [entry for entry in (parse(item, account) for item in items) if entry]
            if not videos:
                raise RuntimeError("No usable video metadata; Notion was not changed")
            pub = existing_pages(pub_source, "Clé Social Lens", f"https://www.tiktok.com/@{account}/video/")
            hist = existing_pages(hist_source, "Clé relevé", f"tiktok:{account}:")
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            brand = brands.get(account, account)
            for vid, url, title, posted, metrics in videos:
                page = write(pub_source, publication(url, title, posted, metrics, brand), pub.get(url))
                pub[url] = page["id"]
                key, props = history(account, vid, url, title, metrics, stamp)
                snapshot = write(hist_source, props, hist.get(key))
                hist[key] = snapshot["id"]
                time.sleep(0.35)
            print(f"@{account}: {len(videos)} publications and daily snapshots saved")
        except Exception as exc:
            failed = True
            print(f"@{account}: ERROR {exc}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
