#!/usr/bin/env python3
"""ATS radar: reads employers' official job-board APIs (Greenhouse, Lever, Ashby),
the same data roledar and boardwatch use, filters by profile, diffs against the
last run and writes out/latest.md and out/latest.json. Standard library only.

Usage:
  python ats_radar.py run      # fetch, filter, diff, write out/
  python ats_radar.py probe    # test probe_candidates slugs on each ATS, print hits
"""
import json, sys, os, urllib.request, urllib.error, datetime, re, html

UA = {"User-Agent": "ats-radar/1.0 (personal job search)"}
API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true",
}

# Places that are not UK / UK-remote, checked against the location field only.
# A match here excludes the role, even if the location also mentions the UK
# (e.g. "Canada; United Kingdom; United States" is not a UK-only role).
LOCATION_EXCLUDE = [
    "united states", "usa", "us-based", "u.s.a",
    "canada", "australia", "new zealand", "singapore",
    "north america",
    "south carolina", "north carolina", "maryland", "new york", "california",
    "texas", "florida", "washington", "oregon", "colorado", "illinois",
    "massachusetts", "virginia", "georgia", "ohio", "pennsylvania",
    "arizona", "nevada", "utah", "michigan", "minnesota", "missouri",
    "tennessee", "indiana", "wisconsin", "alabama", "louisiana",
    "kentucky", "oklahoma", "iowa", "kansas", "nebraska", "idaho",
    "montana", "wyoming", "alaska", "hawaii",
    "madrid", "spain", "france", "germany", "netherlands", "india",
]

def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or ""))).strip()

def normalise(ats, token, data):
    out = []
    if ats == "greenhouse":
        for j in data.get("jobs", []):
            out.append({"title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
                        "url": j.get("absolute_url", ""), "updated": j.get("updated_at", ""),
                        "pay": "", "snippet": strip(j.get("content", ""))[:400]})
    elif ats == "lever":
        for j in data:
            cats = j.get("categories") or {}
            sr = j.get("salaryRange") or {}
            pay = f"{sr.get('currency','')} {sr.get('min','')}-{sr.get('max','')} {sr.get('interval','')}".strip() if sr else ""
            out.append({"title": j.get("text", ""), "location": cats.get("location", "") + (" " + j.get("workplaceType", "") if j.get("workplaceType") else ""),
                        "url": j.get("hostedUrl", ""), "updated": str(j.get("createdAt", "")),
                        "pay": pay, "snippet": strip(j.get("descriptionPlain") or j.get("description", ""))[:400]})
    elif ats == "ashby":
        for j in data.get("jobs", []):
            if j.get("isListed") is False:
                continue
            comp = (j.get("compensation") or {}).get("compensationTierSummary", "") or ""
            loc = j.get("location", "") + (" Remote" if j.get("isRemote") else "")
            out.append({"title": j.get("title", ""), "location": loc, "url": j.get("jobUrl", ""),
                        "updated": j.get("publishedAt", ""), "pay": comp,
                        "snippet": strip(j.get("descriptionPlain") or "")[:400]})
    for o in out:
        o["ats"], o["board"] = ats, token
    return out

def matches(job, prof):
    t, loc = job["title"].lower(), job["location"].lower()
    if not any(k in t for k in prof["title_keywords"]):
        return False
    if any(k in t for k in prof.get("title_exclude", [])):
        return False
    # Location is checked against the location field only, never the title.
    # Previously "remote" (or "uk") in a title passed a US role.
    if any(k in loc for k in LOCATION_EXCLUDE + prof.get("location_exclude", [])):
        return False
    return any(k in loc for k in prof["location_keywords"])

def load_seen():
    """Seen history, kept separately from latest.json so a lost or corrupt
    latest.json does not re-flood with every previous match as 'new'.
    Format: {profile: {url: {"title": str, "location": str, "first_seen": date}}}
    Falls back to latest.json all_urls (title/location unknown) on first run.
    """
    try:
        with open("out/seen.json") as f:
            return json.load(f)
    except Exception:
        pass
    seen = {}
    try:
        prev = json.load(open("out/latest.json"))
        for name, p in prev.get("profiles", {}).items():
            seen[name] = {u: {"title": "", "location": "", "first_seen": prev.get("date", "")}
                          for u in p.get("all_urls", [])}
    except Exception:
        pass
    return seen

def run(cfg):
    os.makedirs("out", exist_ok=True)
    seen = load_seen()
    today = datetime.date.today().isoformat()
    run_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = {"date": today, "run_at_utc": run_at, "profiles": {}, "errors": []}
    md = [f"# ATS radar {today}", "", "New since the last run, from employers' own job boards (Greenhouse, Lever, Ashby APIs).", ""]
    for name, prof in cfg["profiles"].items():
        hits = []
        for b in prof["boards"]:
            try:
                jobs = normalise(b["ats"], b["token"], get_json(API[b["ats"]].format(t=b["token"])))
            except Exception as e:
                result["errors"].append(f"{b['ats']}/{b['token']}: {e}")
                continue
            hits += [j for j in jobs if matches(j, prof)]
        profile_seen = seen.setdefault(name, {})
        new = []
        for j in hits:
            if j["url"] not in profile_seen:
                profile_seen[j["url"]] = {"title": j["title"], "location": j["location"], "first_seen": today}
                new.append(j)
            else:
                # Keep the stored title/location if the board now returns less.
                stored = profile_seen[j["url"]]
                if not stored.get("title"):
                    stored["title"] = j["title"]
                if not stored.get("location"):
                    stored["location"] = j["location"]
        # Full triageable list, not just URLs: title + location + first_seen.
        all_jobs = [{"title": profile_seen[u]["title"], "location": profile_seen[u]["location"],
                     "url": u, "first_seen": profile_seen[u].get("first_seen", "")}
                    for u in sorted({j["url"] for j in hits})]
        result["profiles"][name] = {"matched": len(hits), "new": new,
                                     "all_urls": sorted({j["url"] for j in hits}),
                                     "all_jobs": all_jobs}
        md += [f"## {name}: {len(new)} new ({len(hits)} matching in total)", ""]
        for j in new:
            pay = f" | {j['pay']}" if j["pay"] else ""
            md.append(f"- [{j['title']}]({j['url']}) | {j['board']} ({j['ats']}) | {j['location']}{pay}")
        md.append("")
    if result["errors"]:
        md += ["## Boards that failed", ""] + [f"- {e}" for e in result["errors"]] + [""]
    json.dump(result, open("out/latest.json", "w"), indent=1)
    json.dump(seen, open("out/seen.json", "w"), indent=1)
    open("out/latest.md", "w").write("\n".join(md))
    open(f"out/{today}.md", "w").write("\n".join(md))
    print("\n".join(md))

def probe(cfg):
    for slug in cfg.get("probe_candidates", []):
        for ats, url in API.items():
            try:
                d = get_json(url.format(t=slug), timeout=15)
                n = len(d) if isinstance(d, list) else len(d.get("jobs", []))
                print(f"HIT {ats} {slug} {n} jobs")
            except Exception:
                pass

if __name__ == "__main__":
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")))
    {"run": run, "probe": probe}.get(sys.argv[1] if len(sys.argv) > 1 else "run", run)(cfg)
