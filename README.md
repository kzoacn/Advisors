# Advisors

Advisors is an open-data project for source-traceable Chinese university faculty
profile data.

The first stage focuses on public official faculty profile pages from:

- 清华大学
- 北京大学
- C9 universities

The core public output is versioned Parquet data. Local page caches are maintained
as a reproducible fact layer, but raw HTML caches are not part of public releases
by default.

## Current Scope

- Use official university, school, department, lab, and faculty profile system pages.
- Keep source URL, fetch time, content hash, and cache path for every cached page.
- Exclude all phone numbers from structured outputs.
- Store homepage-listed projects, funding, publications, patents, and honors as text
  sections until later schema work.
- Generate cooperation networks later; they are not first-stage fact data.

See [plan.md](plan.md) for the full project plan.

## Data Layout

Each university has its own working and cache directory:

- `data/cache/<school>/`: cached source pages and metadata.
- `data/working/<school>/`: discovered registries, intermediate extracted tables, quality reports, and releases.
- `data/working/<school>/release-<school>-v0.1.0/`: public Parquet release package.

Cross-school summaries such as `release_summary_v0.1.0.csv` stay in `data/working/`.

Current school slugs include `thu`, `pku`, `fdu`, `sjtu`, `nju`, `zju`,
`ustc`, `hit`, and `xjtu`.

## Development

Install the package in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
python -m pytest -q
```

Validate the initial source registry:

```bash
advisors validate-registry --sources configs/sources.yaml
```

Seed a coverage ledger:

```bash
advisors seed-coverage \
  --sources configs/sources.yaml \
  --out data/working/coverage.csv
```

Cache seed source pages:

```bash
advisors cache-sources \
  --sources configs/c9_sources.yaml \
  --university pku \
  --out data/working/pku/source_pages_seed.parquet
```

Extract structured Parquet tables from cached page text:

```bash
advisors extract-cache \
  --sources data/working/pku/discovered_profiles.yaml \
  --out-dir data/working/pku/extracted
```

By default, `extract-cache` only processes cached pages whose source type is a
teacher profile. Faculty list pages and portals remain cached as source facts but
are not treated as single-person profiles.

Write a release manifest:

```bash
advisors write-manifest \
  --release-dir release/v0.1.0 \
  --dataset-version v0.1.0 \
  --schema-version 0.1.0 \
  --university 清华大学 \
  --university 北京大学
```
