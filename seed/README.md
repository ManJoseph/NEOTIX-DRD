# Seed data

- `episodes.csv` — export from our recording system. It is intentionally messy (duplicates, blank and invalid values, inconsistent casing/whitespace, mixed date formats, an unknown robot, a malformed row). Decide how each case should be handled, handle it, and report it. Document your decisions in NOTES.md.
- Reviewer users are created by `manage.py seed_reviewers` during startup. README lists the usernames; generated passwords are stored only in ignored `.run/reviewer-accounts.json`. The supplied `users.json` remains local and excluded from Git; it is not the published credential source.

Known robots: `arm-01`, `arm-02`, `arm-03`, `mobile-01`, `humanoid-01`.
- `generate_episodes.py` — produces a large *clean* CSV (e.g. `python3 generate_episodes.py 200000 > episodes_large.csv`) if you want to see how your import and analytics behave with real volume. Optional.
