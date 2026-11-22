# ATS radar

Daily check of employers' own job boards through their official public APIs
(Greenhouse, Lever, Ashby), the same data source roledar and boardwatch use.
Runs free on GitHub Actions every morning at 06:17 UTC and writes:

- out/latest.md   new matching roles since the last run, with links
- out/latest.json same data for the Claude daily alerts

Profiles in config.json:
- finance_ai: AI trainer / expert roles in finance, investment, humanities, classics, writing, generalist
- green_early_career: entry-level ESG, policy, ecology, comms roles (boards added after `probe`)

Edit config.json to add boards: {"ats": "greenhouse" | "lever" | "ashby", "token": "<board slug>"}.
`python ats_radar.py probe` tests the slugs in probe_candidates and prints which ones exist.

## One-time setup: paste this into Claude Code on your laptop

Set up my ATS radar repo from the folder I downloaded (ats-radar). Steps:
1. Make sure the GitHub CLI is logged in as my account (run `gh auth status`; if it is not, run `gh auth login` and let me sign in in the browser).
2. Create a new PUBLIC GitHub repo called ats-radar under my account from this folder, and push it to main. Public is needed so my Claude daily alerts can read out/latest.md without a password; it contains only job listings and search keywords, no personal data.
3. Run `python ats_radar.py probe` locally. For every HIT line, add that board to the green_early_career profile in config.json (and to finance_ai if it is an AI training or finance company). Commit and push.
4. In the repo's Actions tab, enable workflows if asked, then run the "ATS radar" workflow once with workflow_dispatch (`gh workflow run "ATS radar"`), wait for it to finish (`gh run watch`), and confirm out/latest.md was committed.
5. Tell me the raw URL of out/latest.md (https://raw.githubusercontent.com/<my user>/ats-radar/main/out/latest.md).
Do not add any secrets, tokens or personal details to the repo.
