"""Optional stock video for the hook, from Pexels (free licence, needs PEXELS_API_KEY)."""
import requests


def fetch(cfg, query, dest):
    key = cfg["secrets"]["pexels"]
    if not key or not query:
        return None
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait", "per_page": 5}, timeout=30)
        r.raise_for_status()
        for video in r.json().get("videos", []):
            files = [f for f in video.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 1280]
            if files:
                best = min(files, key=lambda f: f["height"])
                data = requests.get(best["link"], timeout=120)
                data.raise_for_status()
                dest.write_bytes(data.content)
                return dest
    except (requests.RequestException, ValueError, KeyError) as e:
        print("b-roll: skipped,", e)
    return None
