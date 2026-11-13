#!/usr/bin/env python3
"""Post due reels to Instagram, straight from GitHub Actions - no Claude session involved.

reels/queue.json is a list of entries:
  {"id": "mw06", "file": "ig_mw06_boobie.mp4", "cover": "SixStar_Thumb_mw06.jpg",
   "caption": "...", "comment": "first comment, optional", "post_at": "2026-11-13T14:00:00Z"}
An entry is posted once its post_at has passed. On success the entry gets "posted_at",
"media_id" and "permalink" written back, so a later run never posts it twice.

Entries more than MAX_LATE hours overdue are skipped and reported, so a long outage cannot
dump yesterday's reels into the feed at 3 in the morning.

Env: IG_USER_ID, IG_ACCESS_TOKEN, optional IG_API_BASE, PAGES_BASE, MAX_LATE (hours, default 6), DRY_RUN=1
"""
import json, os, sys, time, urllib.parse, urllib.request, datetime

# Host depends on how the token was made: a Facebook-Login / Page token talks to graph.facebook.com,
# a token from "Instagram business login" talks to graph.instagram.com. Set IG_API_BASE to switch.
API = os.environ.get('IG_API_BASE', 'https://graph.facebook.com/v21.0').rstrip('/')
UID = os.environ.get('IG_USER_ID', '').strip()
TOK = os.environ.get('IG_ACCESS_TOKEN', '').strip()
PAGES = os.environ.get('PAGES_BASE', 'https://ericjunger3-cmd.github.io/gosixstar_media').rstrip('/')
MAX_LATE = float(os.environ.get('MAX_LATE', 6))
DRY = os.environ.get('DRY_RUN') == '1'
QUEUE = 'reels/queue.json'
now = datetime.datetime.now(datetime.timezone.utc)


def call(path, params, post=False, tries=3):
    """One Graph API call with retries on network and 5xx errors."""
    params = dict(params, access_token=TOK)
    for attempt in range(1, tries + 1):
        try:
            if post:
                rq = urllib.request.Request(f'{API}/{path}', data=urllib.parse.urlencode(params).encode())
            else:
                rq = urllib.request.Request(f'{API}/{path}?' + urllib.parse.urlencode(params))
            with urllib.request.urlopen(rq, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:400]
            if e.code < 500 or attempt == tries:
                raise RuntimeError(f'HTTP {e.code} on {path}: {body}') from None
            print(f'  HTTP {e.code}, retry {attempt}', flush=True)
        except Exception as e:
            if attempt == tries:
                raise RuntimeError(f'{type(e).__name__} on {path}: {e}') from None
            print(f'  {type(e).__name__}, retry {attempt}', flush=True)
        time.sleep(15 * attempt)


def publish(e):
    """Container -> wait for FINISHED -> publish -> first comment -> permalink."""
    p = {'media_type': 'REELS', 'video_url': f"{PAGES}/reels/{e['file']}",
         'caption': e.get('caption', ''), 'share_to_feed': 'true'}
    if e.get('cover'):
        p['cover_url'] = f"{PAGES}/thumbs/{e['cover']}"
    cid = call(f'{UID}/media', p, post=True)['id']
    print(f"  container {cid}", flush=True)

    for _ in range(40):                       # Instagram transcodes; usually well under a minute
        time.sleep(15)
        st = call(cid, {'fields': 'status_code,status'})
        code = st.get('status_code')
        if code == 'FINISHED':
            break
        if code == 'ERROR':
            raise RuntimeError(f"container failed: {st.get('status')}")
    else:
        raise RuntimeError('container still not FINISHED after 10 minutes')

    mid = call(f'{UID}/media_publish', {'creation_id': cid}, post=True)['id']
    print(f"  published {mid}", flush=True)

    if e.get('comment'):
        try:
            call(f'{mid}/comments', {'message': e['comment']}, post=True)
        except Exception as ex:               # the reel is live; a failed comment must not retry the post
            print(f'  comment failed: {ex}', flush=True)
    try:
        link = call(mid, {'fields': 'permalink'}).get('permalink', '')
    except Exception:
        link = ''
    return mid, link


def main():
    if not os.path.exists(QUEUE):
        print('no queue'); return 0
    Q = json.load(open(QUEUE))
    if not UID or not TOK:
        print('IG_USER_ID / IG_ACCESS_TOKEN missing', file=sys.stderr); return 1

    posted, failed, late, report = [], [], [], False
    for e in Q:
        if e.get('posted_at') or not e.get('post_at') or e.get('gave_up'):
            continue
        due = datetime.datetime.fromisoformat(e['post_at'].replace('Z', '+00:00'))
        if due > now:
            continue
        hours = (now - due).total_seconds() / 3600
        if hours > MAX_LATE:
            e['skipped'] = f'{hours:.1f} h overdue'
            e['gave_up'] = True; report = True
            late.append(e.get('id') or e['file']); continue
        print(f"posting {e.get('id') or e['file']} ({hours:.1f} h after its slot)", flush=True)
        if DRY:
            print('  dry run'); continue
        try:
            mid, link = publish(e)
            e['posted_at'] = now.isoformat().replace('+00:00', 'Z')
            e['media_id'] = mid
            if link:
                e['permalink'] = link
            posted.append(f"{e.get('id') or e['file']} {link}")
        except Exception as ex:
            e['last_error'] = str(ex)[:300]
            e['tries'] = e.get('tries', 0) + 1
            failed.append(f"{e.get('id') or e['file']}: {ex}")
            print(f'  FAILED: {ex}', flush=True)
            if e['tries'] >= 5:                 # stop retrying every 10 minutes forever
                e['gave_up'] = True
            if e['tries'] in (1, 5):            # report the first failure and the final one, nothing between
                report = True

    json.dump(Q, open(QUEUE, 'w'), ensure_ascii=False, indent=1)
    out = {'posted': posted, 'failed': failed, 'skipped_too_late': late}
    print(json.dumps(out, ensure_ascii=False))
    if gh := os.environ.get('GITHUB_OUTPUT'):
        with open(gh, 'a') as f:
            f.write(f"posted={len(posted)}\nfailed={len(failed)}\nlate={len(late)}\nreport={'1' if report else '0'}\n")
            f.write('summary=' + json.dumps(out, ensure_ascii=False).replace('\n', ' ') + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
