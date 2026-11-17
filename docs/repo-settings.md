# Repository settings (admin checklist)

Settings an admin applies by hand; they cannot be committed. Decided Nov 13, 2026 (decision record D5–D7). Apply the same
settings to both repositories: gmi-savings-tracker (flagship, v1) and gmi-savings-tracker-v3 (testing ground).

| Setting | Where | Value | Why |
|---|---|---|---|
| Branch ruleset on `main` | Settings → Rules → Rulesets → New ruleset → Import a ruleset: `.github/rulesets/main.json` | Require a pull request; require the `test` status check (CI), up to date with `main`; block force pushes; restrict deletions | [Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| Dependabot alerts and security updates | Settings → Code security | Dependency graph on; Dependabot alerts on; Dependabot security updates on | [About Dependabot alerts](https://docs.github.com/en/code-security/dependabot/dependabot-alerts/about-dependabot-alerts) |
| Automatically delete head branches | Settings → General → Pull Requests | On | Merged branches are removed after each pull request |
| Socrata app token | data.maryland.gov → sign in → Developer settings → Create new app token; then Settings → Secrets and variables → Actions → `MD_SODA_APP_TOKEN` (and the local `.env`) | One token for the pipeline | Tokenless requests share a throttled IP pool ([Application Tokens](https://dev.socrata.com/docs/app-tokens)); `make extract-scheduled` and the CI extract stop without it |
| Pages deploy | Settings → Pages → Source: GitHub Actions | Only `.github/workflows/pages.yml` deploys | v2's `static.yml` uploaded the whole repository and shared the `pages` deploy group with `pages.yml`; delete it in v2 |
| About: description, website, topics | Repo home page > About (gear icon), or `gh repo edit` | Description: "Independent, audit-grade check of Maryland's Government Modernization Initiative savings, built only on the State's open data: SODA to DuckDB, forecasts with calibrated ranges, detector backtests, and reconciliation to the State's budget books." Website: the Pages URL. Topics: `data-science`, `duckdb`, `mlops`, `public-policy`, `maryland`, `open-data`, `government-transparency`, `forecasting`, `conformal-prediction`, `lightgbm`, `data-engineering`, `python`, `parquet`, `model-context-protocol` | The repository is found by search and says what it is before anyone opens it |
| Discussions | Settings > General > Features > Discussions; then Settings > Discussions categories | On, with only **Q&A** and **Ideas** (delete Announcements, General, Polls and Show and tell) | Questions and ideas have a home; the issue chooser (`.github/ISSUE_TEMPLATE/config.yml`) links to both categories, so enable this first |
| Social preview | Settings > General > Social preview | Upload `docs/figures/readme/overview.png` cropped to 1280 x 640 | Links shared on social sites show the dashboard, not a blank card |
