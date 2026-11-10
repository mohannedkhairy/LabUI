# Nanobubble publication scout

The dashboard's **Nanobubble scout** runs automatically at startup when due, then
every seven days. No dashboard visit, button click, or recurring user interaction
is required. **All reports** opens `/research/scout`, where discoveries have
titles, authors, publication dates, journal names, original source abstracts when
available, DOI/paper links, and source provenance. **Scan now** starts an immediate
background scan. Reports count newly discovered publications; repeated sightings
update metadata without appearing as new discoveries.

## Sources and search

- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/):
  journal articles, proceedings, book chapters, and posted content registered with
  Crossref. Searches four spelling variants separately and follows cursor pages.
- [Europe PMC](https://europepmc.org/RestfulWebService): articles and preprints in
  its biomedical/life-science index, including nanobubble applications in medicine
  and biology. Uses core records with available abstracts and cursor pagination.
- [arXiv API](https://info.arxiv.org/help/api/user-manual.html): new preprints,
  using the submission date window and paginated Atom results.

Queries cover **nanobubble**, **nano bubbles**, **ultrafine bubbles**, and
**ultra fine bubbles**. A result must also mention a nanobubble/ultrafine bubble
variant in its title or abstract. Matching includes singular/plural forms and
hyphenation. General microbubble-only papers are excluded.

**Every scan searches only the previous seven complete UTC dates.** A scan on
2026-11-06 covers 2026-10-30 through 2026-11-05, inclusive. The current partial day
is covered by the next weekly scan. This same rule applies to the first scan,
manual scans, automatic retries, and overdue runs after downtime. The window
never widens to retrieve older publications or backfill missed weeks.

Crossref requests bounded `from-pub-date`/`until-pub-date` filters, Europe PMC
uses bounded `FIRST_PDATE`, and arXiv uses bounded `submittedDate`. Indexing dates
and source checkpoints do not determine eligibility. A second local filter checks
every result against both publication-date boundaries. Old papers newly indexed
this week do not qualify. Dates from the current day, future dates, invalid dates,
missing dates, and year/month-only dates are excluded. Reports store their exact
window and each source's rejected-date count.

Published dates are distinct from the date LabUI found a paper. Online publication
dates take priority over print issue dates. Source abstracts are displayed as
plain text; the scout does not generate claims about findings. The dashboard and
default publication listing show only the current seven-day window. Historical
reports remain available when explicitly selected; existing reports created under
the earlier wider policy are labeled as historical.

Duplicates join by normalized DOI, source identifier (arXiv version suffixes are
removed), or exact normalized title plus first author and publication class for
DOI-less records. Conflicting DOIs remain separate. Preprints and journal versions
remain separate; `arxiv:doi` points to the journal version and is not used as the
preprint's identity. The scout keeps its own discovery collection; it does not
download PDFs or add records to the indexed PDF library.

These indexes cannot guarantee every publication on the web. Publisher indexing
lags, missing abstracts, unusual terminology, and publications absent from the
indexes can affect coverage. The strict date policy also excludes papers whose
exact publication date cannot be established from source metadata and late-indexed
papers outside the seven-day window. Reports show which sources finished. A page
limit (20 × 100 records per query), a failed page, or malformed response marks
coverage incomplete rather than silently treating the scan as successful. Results
already obtained are retained. Blog posts, patents, product announcements, and
general news are outside this publication scout's current scope.

## Scheduling and storage

Storage is `$JFR_DATA_DIR/publication_scout.sqlite`, alongside the journal-fit
database, with additive tables in a separate SQLite file. The local RAG database,
PDFs, models, and vector indexes are not involved. No API keys or new dependencies
are required. Outgoing requests contain the public topic/date queries.

The app checks for a due scan every minute while running. Schedule, success markers,
discoveries, and reports survive service restarts. An overdue scan runs at the
next startup. A complete scan schedules the next one seven days after completion;
an incomplete/failed scan retries after one hour. A manual scan updates the same
schedule. A shared SQLite lease prevents overlapping runs across app workers;
abandoned runs are recovered after 30 minutes without a heartbeat. A normal
shutdown releases the active scan so the next startup can retry immediately.
Network calls have timeouts, bounded retries, and backoff for rate limits/server
failures.

`LABUI_SCOUT_ENABLED=0` pauses automatic scans; manual scanning still works. The
default is enabled. The host must be awake and LabUI running for scheduled scans.
After updating the checkout, load the feature with:

```bash
systemctl --user restart labui
```

The existing private-access middleware also covers the scout pages and API.

## API and verification

- `GET /api/scout/status`: schedule, latest report, source results, total discoveries.
- `POST /api/scout/run`: queue a scan (202), or report an existing scan (200).
- `GET /api/scout/reports?limit=30`: recent reports (maximum 100).
- `GET /api/scout/papers?run_id=1&offset=0&limit=50`: paginated discoveries;
  omit `run_id` for publications in the current seven-day window.
- `GET /research/scout?run_id=1`: an individual saved report.

Run the isolated regression checks without contacting external APIs:

```bash
PYTHONPATH=.:submission_strategy submission_strategy/.venv/bin/python \
  -m unittest discover -s tests -p test_publication_scout.py -v
```

API behavior references: [Crossref pagination and date-filter guidance](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/),
[Europe PMC API](https://europepmc.org/RestfulWebService), and the
[arXiv API manual](https://info.arxiv.org/help/api/user-manual.html).
