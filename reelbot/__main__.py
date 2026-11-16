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
        print("Claude:", "set" if claude.available(cfg) else "MISSING")
        if not ig.ready:
            print("Instagram: IG_USER_ID / IG_ACCESS_TOKEN MISSING")
        else:
            me = ig.me()
            print(f"Instagram: @{me.get('username')} followers {me.get('followers_count')}")
            print("Publish quota:", ig.publish_quota())
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
