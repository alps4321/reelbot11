"""Finds top-performing reels for the topic through the official Graph API.

Two sources: top media under the hashtags in config.yaml, and recent reels of
named competitor accounts. Only captions and public counts are read; the bot
learns which subjects and hooks work, it never copies or downloads a video.
"""
from . import store
from .instagram import IGError


def _is_reel(m):
    return m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO"


def _item(m, source):
    likes, comments = m.get("like_count") or 0, m.get("comments_count") or 0
    return {
        "source": source,
        "permalink": m.get("permalink", ""),
        "caption": (m.get("caption") or "").strip()[:400],
        "likes": likes, "comments": comments, "views": m.get("view_count") or 0,
        "engagement": likes + 3 * comments,
        "timestamp": m.get("timestamp", ""),
    }


def stale(cfg):
    r = store.read("research", {})
    if not r.get("updated"):
        return True
    age = (store.now() - store.parse(r["updated"])).total_seconds() / 86400
    return age >= cfg["research"]["refresh_days"]


def refresh(cfg, ig):
    if not ig.ready:
        print("research: no Instagram credentials, skipped")
        return
    items, errors = [], []
    for tag in cfg["research"]["hashtags"]:
        try:
            items += [_item(m, f"#{tag}") for m in ig.hashtag_top(tag) if _is_reel(m)]
        except (IGError, KeyError, IndexError) as e:
            errors.append(f"#{tag}: {e}")
    for user in cfg["research"]["competitors"]:
        try:
            _, media = ig.discover(user)
            items += [_item(m, f"@{user}") for m in media if _is_reel(m)]
        except (IGError, KeyError) as e:
            errors.append(f"@{user}: {e}")

    seen, unique = set(), []
    for it in sorted(items, key=lambda x: x["engagement"], reverse=True):
        if it["permalink"] not in seen and it["caption"]:
            seen.add(it["permalink"])
            unique.append(it)
    if not unique and errors:
        print("research: nothing fetched;", "; ".join(errors[:3]))
        return  # keep the previous research rather than wiping it
    store.write("research", {"updated": store.iso(), "errors": errors,
                             "items": unique[: cfg["research"]["keep_top"]]})
    print(f"research: kept {len(unique[: cfg['research']['keep_top']])} reels, {len(errors)} source errors")


def digest(limit=12):
    """Short text block of what is working in the niche, for the script prompt."""
    items = store.read("research", {}).get("items", [])[:limit]
    return "\n".join(
        f"- [{i['source']}] likes {i['likes']}, comments {i['comments']}"
        + (f", views {i['views']}" if i["views"] else "")
        + f": {i['caption'][:220].replace(chr(10), ' ')}"
        for i in items
    )
