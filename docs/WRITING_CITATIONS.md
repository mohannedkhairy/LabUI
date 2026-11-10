# Writing citations

Type **`@`** in a writing section to open paper suggestions. Continue with an
author surname, a citation key prefix, or a word from a title. For example,
**`@cai`** finds `@cai2024`, *Investigating the Potential of CO2 Nanobubble Systems
for Enhanced Oil Recovery in Extra-Low-Permeability Reservoirs*. First-author/key
prefix matches rank before matches in coauthors or other fields. Each suggestion
shows its key, title, authors, and year. Use arrows and Enter/Tab, or click a
suggestion, to insert its complete key. Escape closes the list.

Suggestions begin with the bare `@` or one letter. The query is debounced and
outdated responses are discarded if typing continues, the cursor moves, or the
section changes. Email addresses and inline code examples do not open the picker.
The Cite toolbar button provides the same searchable catalog.

## Keys and stored identities

The citation key is **first-author surname + publication year**, such as
`cai2024` or `khairy2025`. Additional library records with the same base receive
`a`, `b`, … suffixes. Existing suffixes remain stable. A missing year is explicit:
`caind`; a missing usable author becomes `anon2024` or `anonnd`. Missing metadata
is not guessed. Metadata corrections update the key while preserving its previous
spelling as an alias.

`papers.paper_id` remains the internal identity used by PDFs, passages, vectors,
and other library features. `citation_catalog.citation_key` is the short writing
token. Changing the writing key does not rename PDFs or reindex documents. The
`@` character is syntax, not part of the stored key.

Old citation keys, external aliases, and internal paper IDs continue to resolve.
All variants identify one reference within a project, share its number, and work
in preview and export. Tokens match exactly, so `@cai2024a` cannot accidentally
become `@cai2024` followed by an `a`. The reference list displays each cited
record once. Separate PDF/library records, including proof copies, are preserved;
this migration does not merge or delete them. Orphaned catalog records without
an indexed paper are excluded from suggestions; standalone imported references
remain available.

The writing source stores `@key`. Preview and manuscript exports retain the
existing numbered `[1]` citation format; BibTeX exports use the short author/year
keys. The inserted citation is saved before project-wide numbering refreshes.

## Migration and maintenance

Startup and citation search synchronize metadata and migrate legacy keys once.
The first migration creates a SQLite snapshot under
`$RAG_DATA_DIR/citation-key-backups/` before changing existing keys. A policy marker
avoids repeated migrations during typing. Previous spellings are retained in
`aliases_json`; database record IDs and paper contents are preserved.

For an explicit, reviewable migration, preview with:

```bash
submission_strategy/.venv/bin/python tools/migrate_citation_keys.py \
  --db /path/to/rag.db --audit /path/to/audit
```

Add `--apply` to create a database snapshot, apply the changes, verify that all
paper rows are unchanged and old keys remain aliases, and write an audit result.
Already migrated databases produce an empty plan.

The editor loads `/static/writing_citations.js`; reload the writing page after
updating it. Restart an already running LabUI process to load Python changes:

```bash
systemctl --user restart labui
```

## Verification

```bash
PYTHONPATH=.:submission_strategy:Local_Rag/rag submission_strategy/.venv/bin/python \
  -m unittest discover -s tests -p test_writing_citations.py -v
node tests/writing_citations.test.cjs
```

The completion integration follows CodeMirror 5's
[instance `showHint(options)` API](https://github.com/codemirror/codemirror5/blob/5.65.16/addon/hint/show-hint.js).
