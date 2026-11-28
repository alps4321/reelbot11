"""When our followers are online, and who watches: Instagram's own account numbers (aggregated, no personal data).

Writes stats-data/audience.json for the dashboard and the posting-time review. Each metric is asked for on its
own, so one that Instagram refuses (online_followers needs 100+ followers) does not stop the rest.
"""
import json
import time
from pathlib import Path

from .instagram import IGError

OUT = Path("stats-data") / "audience.json"


def _try(ig, label, **params):
    try:
        return ig._call("GET", f"{ig.uid}/insights", **params).get("data", [])
    except IGError as e:
        print(f"{label}: not available ({e})")
        return None


def run(cfg, ig):
    me = ig.me()
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "followers": me.get("followers_count"),
           "media": me.get("media_count")}
    print(f"followers: {out['followers']}, media: {out['media']}")
    online = _try(ig, "online_followers", metric="online_followers", period="lifetime")
    if online:
        days = online[0].get("values", [])
        hours = {}
        for d in days:
            for h, n in (d.get("value") or {}).items():
                hours.setdefault(int(h), []).append(n)
        out["online_followers"] = {"days": len(days), "end_times": [d.get("end_time") for d in days][-3:],
                                   "avg_by_hour": {h: round(sum(v) / len(v), 1) for h, v in sorted(hours.items())}}
        print("online_followers (Instagram's hour keys, averaged over", len(days), "days):", out["online_followers"]["avg_by_hour"])
    since, until = int(time.time()) - 28 * 86400, int(time.time())
    for metric, breakdown in (("views", "follow_type"), ("reach", "follow_type"), ("views", "media_product_type")):
        d = _try(ig, f"{metric} by {breakdown}", metric=metric, period="day", metric_type="total_value",
                 breakdown=breakdown, since=since, until=until)
        if d:
            res = (d[0].get("total_value") or {}).get("breakdowns", [{}])[0].get("results", [])
            out[f"{metric}_by_{breakdown}"] = {"/".join(r.get("dimension_values", [])): r.get("value") for r in res}
            print(f"{metric} by {breakdown} (28 days):", out[f"{metric}_by_{breakdown}"])
    for br in ("city", "country", "age", "gender"):
        d = _try(ig, f"follower_demographics by {br}", metric="follower_demographics", period="lifetime",
                 metric_type="total_value", breakdown=br, timeframe="this_month")
        if d:
            res = (d[0].get("total_value") or {}).get("breakdowns", [{}])[0].get("results", [])
            top = sorted(res, key=lambda r: -r.get("value", 0))[:8]
            out[f"followers_by_{br}"] = {"/".join(r.get("dimension_values", [])): r.get("value") for r in top}
            print(f"followers by {br}:", out[f"followers_by_{br}"])
    if OUT.parent.exists():
        OUT.write_text(json.dumps(out, indent=1))
    return out
