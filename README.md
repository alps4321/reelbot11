# ReelBot for iLoveDocuments

## Daily plan (current)

- Runs on GitHub three times a day (12:37 pm, 6:37 pm, 9:07 pm India time). Each run reads the results of
  earlier reels, then makes and posts one reel: Hinglish, English, Hinglish.
- Week 1: a different tool from ilovedocuments.ai in every post (45 tools, ordered by how often Indians search
  for them).
- From week 2: Tuesday and Friday all go to the best-scoring tool. Other days: one proven tool (top 5,
  rotating) and one tool that has had the fewest posts; the third post alternates.
- Reels are compared at the same age (48 hours). Score weighs shares and saves most, and rewards watch time.
- Voice: one consistent male narrator (OmniVoice, copied from `assets/voices/hi_male_ref.wav`), spoken one
  phrase per breath with real pauses after sentences and longer pauses after questions and before the answer.
- Results: `data/report.md`. Reels posted by hand are picked up and tracked too.

Makes two faceless Instagram Reels a day about ilovedocuments.ai (one English, one
Hinglish), posts them, reads the results, and uses them to decide the next reel. No server needed: it runs on a free
GitHub Actions schedule.

## What happens on every run

1. **Measure**: reads views, reach, likes, comments, shares, saves and watch time for
   earlier reels (at 24 hours, 72 hours and 7 days).
2. **Learn**: averages a score per topic and per hook style. Claude turns the results
   table into "keep / avoid / test next" rules (`data/playbook.json`).
3. **Research**: every 3 days, pulls top reels for your hashtags and competitor
   accounts through Instagram's official API (`data/research.json`).
4. **Plan**: picks the topic and hook style that score best, and 25% of the time
   tests something new.
5. **Script**: Claude writes an original script and caption. The script is checked
   (length, structure, allowed claims) before anything is made.
6. **Produce**: AI voiceover, text that pops in word by word, animated cards (upload
   error, file size dropping, upload success), sound effects, word-by-word captions,
   optional stock video behind the hook, 1080x1920 MP4.
7. **Post**: uploads the reel to Instagram.
8. **Report**: writes `data/report.md` with every reel and its numbers.

## Setup (one time)

### 1. Instagram
- Switch the Instagram account to **Business** or **Creator** and link it to a
  Facebook Page.
- At developers.facebook.com create an app (type: Business) and add the
  **Instagram** product, "API setup with Facebook login".
- In Graph API Explorer generate a token with: `instagram_basic`,
  `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`,
  `pages_read_engagement`.
- Make it long-lived. A normal long-lived token expires after about 60 days; a
  **System User token** (Business Settings > System users) does not expire and is
  the better choice for an unattended bot.
- Get the Instagram user id: `GET /me/accounts?fields=instagram_business_account`.

### 2. Claude
- With a Claude Pro or Max plan: install Claude Code on your computer, run
  `claude setup-token`, and save the token it prints as the secret
  `CLAUDE_CODE_OAUTH_TOKEN`. Scripts then use your plan's usage.
- Or create an API key at console.anthropic.com and save it as `ANTHROPIC_API_KEY`.

### 3. GitHub
- Create a **private** repository and upload this folder.
- Settings > Secrets and variables > Actions, add: `CLAUDE_CODE_OAUTH_TOKEN`,
  `IG_USER_ID`, `IG_ACCESS_TOKEN` (optional `PEXELS_API_KEY`, `ELEVENLABS_API_KEY`).
- Actions tab > ReelBot > Run workflow, tick **dry_run** for the first run and
  download the video from the run page to check it.
- After that it runs daily at 7:00 pm India time. Change the time in
  `.github/workflows/reelbot.yml`.

## Run on your own computer

```
pip install -r requirements.txt      # also needs ffmpeg installed
cp .env.example .env                 # fill in the keys
python -m reelbot check              # confirms the keys work
python -m reelbot make               # makes one reel into out/, no posting
python -m reelbot run                # the full loop
python tests/simulate.py             # 30-day simulation, no keys needed
```

## Things you control in config.yaml

- `posting.enabled`: master off switch. `posting.dry_run`: make but do not post.
- `posting.per_language_per_day`, languages, topics, hook styles, formats, hashtags,
  competitor accounts.
- `content.facts`: the only product claims a script is allowed to make.
- `voice.provider`: `piper` (free) or `elevenlabs` (more natural, paid).
- Brand colours. Put an `.mp3` you have rights to in `assets/music/` for background music.

## Limits to know

- Hashtag research needs Meta's "Instagram Public Content Access" feature. If Meta
  has not granted it to your app, hashtag lookups fail and the bot carries on using
  competitor accounts and your own results.
- Meta allows 30 different hashtags per week for research and a fixed number of API
  posts per day (`python -m reelbot check` shows your quota).
- The bot reads only captions and public counts of other reels. It never downloads
  or reuses anyone's video.
