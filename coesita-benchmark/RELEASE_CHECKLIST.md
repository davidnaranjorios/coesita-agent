# Coesita Benchmark — Release Checklist

Use this before announcing the product publicly or opening sales.

---

## Phase 1 — Repository setup

- [ ] Create a new **private** GitHub repository (e.g. `coesita-benchmark`).
      *Keep it separate from the Hermes Agent fork — this is your commercial IP.*
- [ ] Copy the `coesita-benchmark/` directory into the new repo root
      (not as a subdirectory — GitHub Actions reads workflows from the root).
- [ ] Push to `main`.
- [ ] Verify the `release.yml` workflow appears under **Actions → Workflows**.

## Phase 2 — Legal

- [ ] Review `LICENSE.md` with a lawyer and fill in your name/entity/year.
- [ ] Confirm the FTM v2.2 attribution in the README is accurate
      ("D. Naranjo, *Servitorship Bias*, 2026").
- [ ] If you plan to publish benchmark scores that include third-party model
      outputs, check those models' terms of service for publication clauses.

## Phase 3 — First release

- [ ] Update `__version__` in `src/coesita/__init__.py` to `"1.0.0"`.
- [ ] Tag the commit: `git tag v1.0.0 && git push origin v1.0.0`.
- [ ] Watch the **release** GitHub Actions workflow. It will:
      - Run all 22 tests (must be green).
      - Build `coesita_benchmark-1.0.0-py3-none-any.whl`.
      - Build the Docker image and push to
        `ghcr.io/<your-org>/coesita-benchmark:latest` and `:v1.0.0`.
      - Attach the wheel + Docker tarball to the GitHub Release.
- [ ] Download the wheel from the release page and smoke-test it in a clean venv:
      ```bash
      pip install coesita_benchmark-1.0.0-py3-none-any.whl
      coesita demo
      ```

## Phase 4 — Sales setup

Choose a platform:

### Gumroad (simplest)
- [ ] Create a product: Digital Product, price as per `SALES.md`.
- [ ] Delivery for **Indie tier**: attach the `.whl` file as the download.
- [ ] Delivery for **Team/Enterprise tier**: don't attach a file — use the
      "Redirect to URL" option pointing to a GitHub repository invitation
      (send manually after each sale) or a private download page.
- [ ] Add `SALES.md` content as the product description; use the dashboard
      screenshot (`docs/benchmark-dashboard.png`) as the hero image.

### Lemon Squeezy (recommended for EU VAT handling)
- [ ] Same product structure. Lemon Squeezy handles VAT/taxes automatically.
- [ ] Use Webhooks to automate GitHub repo invitations on purchase.

## Phase 5 — GHCR visibility

- [ ] Go to your GHCR package page → **Package settings → Change visibility**
      → Public (so buyers can `docker pull` without credentials).
      *Or* keep it private and grant access per-buyer via GitHub PAT.

## Phase 6 — Announcement

- [ ] Update the repo README with the real purchase link.
- [ ] Post on LinkedIn / Twitter / HN with:
      - The dashboard screenshot.
      - The two-baseline contrast (CRS 1.000 vs 0.515, FARP 0% vs 67%).
      - The key finding: "average frontier model capitulates 28.7% of the time."
      - A link to the product page.
- [ ] Consider writing a short blog post explaining the FTM v2.2 methodology —
      it doubles as marketing and builds credibility.

---

## Ongoing

- [ ] Run `coesita run --tier research` to reproduce the full 300-scenario
      research figures and include them in the README as social proof.
- [ ] When a new frontier model releases, run the benchmark and post the
      comparison publicly (great organic marketing).
- [ ] For the Enterprise tier, offer a private Slack / email channel for
      questions about extending the corpus.
