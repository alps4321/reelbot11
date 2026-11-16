"""Command line:  python -m reelbot <run|make|check|research|analyze|report>"""
import sys

from . import analyze, config, learn, pipeline, research
from .instagram import Instagram


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    cfg = config.load()
    ig = Instagram(cfg)
    if cmd == "run":            # the full loop; this is what the schedule calls
        pipeline.run(cfg)
    elif cmd == "make":         # build one reel into out/ without posting
        cfg["posting"]["dry_run"] = True
        wanted = sys.argv[2:] or [l["id"] for l in cfg["content"]["languages"]]
        for lang in wanted:
            post = pipeline.make(cfg, learn.next_plan(cfg, lang))
            print(f"out/{post['video']}  {post['seconds']}s  hook: {post['hook']}")
    elif cmd == "check":        # confirm the Instagram and Claude keys work
        from . import claude
        sec = cfg["secrets"]
        kind = ("API key" if sec["anthropic"] else "subscription token" if sec["claude_oauth"].startswith("sk-ant-oat")
                else f"unrecognised value ({len(sec['claude_oauth'])} characters)" if sec["claude_oauth"] else "MISSING")
        print("Claude credential:", kind)
        if claude.available(cfg):
            try:
                print("Claude test call:", claude.ask_json(cfg, "You are a test.", 'Return {"ok": true}', max_tokens=50))
            except Exception as e:
                print("Claude test call: FAILED", str(e)[:300])
        if not ig.ready:
            print("Instagram: IG_USER_ID / IG_ACCESS_TOKEN MISSING")
        else:
            me = ig.me()
            print(f"Instagram: @{me.get('username')} followers {me.get('followers_count')} via {ig.base.split('/')[2]}")
            for name, call in (("publish quota", ig.publish_quota),
                               ("recent media", lambda: ig._call("GET", f"{ig.uid}/media", fields="id,media_product_type,timestamp", limit=3)),):
                try:
                    out = call()
                    print(f"{name}: OK", out if name == "publish quota" else [m.get("id") for m in out.get("data", [])])
                    if name == "recent media" and out.get("data"):
                        print("insights on newest post:", ig.insights(out["data"][0]["id"]) or "NOT AVAILABLE (permission missing?)")
                except Exception as e:
                    print(f"{name}: FAILED {e}")
    elif cmd == "research":
        research.refresh(cfg, ig)
        print(research.digest())
    elif cmd == "analyze":
        analyze.collect(cfg, ig)
        for l in cfg["content"]["languages"]:
            learn.update_playbook(cfg, l["id"])
        analyze.report(cfg)
    elif cmd == "report":
        analyze.report(cfg)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
