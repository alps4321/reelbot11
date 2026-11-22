"""Instagram Graph API (Facebook Login flavour): research, publishing, insights.

Uses only official endpoints. Needs an Instagram Business/Creator account linked
to a Facebook Page, and a token with: instagram_basic, instagram_content_publish,
instagram_manage_insights, pages_show_list, pages_read_engagement.
"""
import os
from datetime import datetime, timezone
import time

import requests


class IGError(RuntimeError):
    pass


class Instagram:
    def __init__(self, cfg):
        s = cfg["secrets"]
        self.uid = s["ig_user_id"]
        self.token = s["ig_token"]
        self.version = s["graph_version"]
        self._base = None
        self.last_usage = 0          # highest % of any Meta rate limit, from the last response's headers

    @property
    def base(self):
        """Meta issues tokens for one of two hosts; find out once which one this token works on."""
        if self._base is None:
            errors = []
            for host in ("graph.facebook.com", "graph.instagram.com"):
                url = f"https://{host}/{self.version}/{self.uid}"
                try:
                    r = requests.get(url, params={"fields": "username", "access_token": self.token}, timeout=30).json()
                except (requests.RequestException, ValueError) as e:
                    errors.append(f"{host}: {e}")
                    continue
                if "username" in r:
                    self._base = f"https://{host}/{self.version}"
                    break
                errors.append(f"{host}: {r.get('error', {}).get('message', r)}")
            else:
                raise IGError("token rejected on both hosts: " + " | ".join(errors))
        return self._base

    @property
    def ready(self):
        return bool(self.uid and self.token)

    def _call(self, method, path, **params):
        params["access_token"] = self.token
        url = path if path.startswith("http") else f"{self.base}/{path}"
        kw = {"params": params} if method == "GET" else {"data": params}
        r = requests.request(method, url, timeout=60, **kw)
        self.last_usage = _usage(r.headers)
        try:
            body = r.json()
        except ValueError:
            raise IGError(f"{r.status_code}: {r.text[:200]}")
        if "error" in body:
            e = body["error"]
            raise IGError(f"{e.get('code')}/{e.get('error_subcode')}: {e.get('message')}")
        return body

    # ---- account -------------------------------------------------------
    def me(self):
        return self._call("GET", self.uid, fields="username,followers_count,media_count")

    def publish_quota(self):
        d = self._call("GET", f"{self.uid}/content_publishing_limit", fields="quota_usage,config")
        return (d.get("data") or [{}])[0]

    # ---- research ------------------------------------------------------
    def hashtag_top(self, tag, limit=25):
        found = self._call("GET", "ig_hashtag_search", user_id=self.uid, q=tag)
        hid = found["data"][0]["id"]
        d = self._call(
            "GET", f"{hid}/top_media", user_id=self.uid, limit=limit,
            fields="id,caption,media_type,media_product_type,like_count,comments_count,permalink,timestamp",
        )
        return d.get("data", [])

    def discover(self, username, limit=25, with_video=False):
        """Public reels of another business/creator account (official Business Discovery endpoint)."""
        extra = ",media_url" if with_video else ""
        fields = (
            f"business_discovery.username({username}){{followers_count,"
            f"media.limit({limit}){{caption,media_type,media_product_type,like_count,"
            f"comments_count,view_count,permalink,timestamp{extra}}}}}"
        )
        try:
            d = self._call("GET", self.uid, fields=fields)["business_discovery"]
        except IGError as e:
            if not (with_video or "view_count" in str(e)):
                raise
            # some accounts refuse a field; ask again with the basic set
            fields = fields.replace(",view_count", "").replace(extra, "")
            d = self._call("GET", self.uid, fields=fields)["business_discovery"]
        return d.get("followers_count", 0), d.get("media", {}).get("data", [])

    # ---- publishing ----------------------------------------------------
    def publish_reel(self, video_path, caption, share_to_feed=True, ai_label=True, thumb_ms=1200, go_live_at=None):
        """Upload, wait for Instagram to process it, then publish (at go_live_at, if that is still ahead)."""
        args = dict(media_type="REELS", upload_type="resumable", caption=caption,
                    share_to_feed="true" if share_to_feed else "false", thumb_offset=thumb_ms)
        size = os.path.getsize(video_path)
        # Instagram's upload server sometimes answers "ProcessingFailedError" for a good file;
        # a fresh container a little later usually goes through, so try up to 3 times
        for attempt in range(3):
            try:
                box = self._call("POST", f"{self.uid}/media", **args,
                                 **({"is_ai_generated": "true"} if ai_label else {}))
            except IGError:
                if not ai_label:
                    raise
                box = self._call("POST", f"{self.uid}/media", **args)
            cid = box["id"]
            uri = box.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{self.version}/{cid}"
            with open(video_path, "rb") as f:
                up = requests.post(uri, data=f, timeout=600, headers={
                    "Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size)})
            if up.status_code == 200 and up.json().get("success", True):
                break
            err = f"upload failed {up.status_code}: {up.text[:200]}"
            if attempt == 2:
                raise IGError(err)
            print(f"{err}; trying again with a new upload in {30 * (attempt + 1)} s")
            time.sleep(30 * (attempt + 1))

        for _ in range(60):  # up to ~5 minutes of processing
            st = self._call("GET", cid, fields="status_code,status")
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise IGError(f"processing failed: {st.get('status')}")
            time.sleep(5)
        else:
            raise IGError("processing timed out")

        if go_live_at:
            wait = (go_live_at - datetime.now(timezone.utc)).total_seconds()
            if wait > 0:
                print(f"instagram: reel uploaded and processed; holding it until {go_live_at:%H:%M} ({wait / 60:.0f} min)",
                      flush=True)
                time.sleep(wait)
        media_id = self._call("POST", f"{self.uid}/media_publish", creation_id=cid)["id"]
        link = self._call("GET", media_id, fields="permalink").get("permalink", "")
        return media_id, link

    # ---- insights ------------------------------------------------------
    METRICS = ["views", "reach", "likes", "comments", "shares", "saved",
               "total_interactions", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]

    def insights(self, media_id):
        def fetch(metrics):
            d = self._call("GET", f"{media_id}/insights", metric=",".join(metrics))
            return {m["name"]: (m.get("values") or [{}])[0].get("value", 0) for m in d.get("data", [])}

        try:
            return fetch(self.METRICS)
        except IGError:
            out = {}
            for m in self.METRICS:  # one metric may be unsupported; keep the rest
                try:
                    out.update(fetch([m]))
                except IGError:
                    pass
            return out


def _usage(headers):
    """Meta reports rate-limit use in two headers as percentages; return the highest one."""
    import json
    top = 0
    for h in ("x-app-usage", "x-business-use-case-usage"):
        raw = headers.get(h)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        rows = [data] if h == "x-app-usage" else [r for v in data.values() for r in v]
        for row in rows:
            top = max([top] + [v for k, v in row.items() if k in ("call_count", "total_cputime", "total_time")
                               and isinstance(v, (int, float))])
    return top
