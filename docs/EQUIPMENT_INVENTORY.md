# Equipment inventory

Open **Lab → Equipment inventory** (`/equipment`). Add an instrument with its
description, category, manufacturer/model, serial number, asset tag, location,
responsible person, status, and supplier/support details. Only its name is
required. Asset tags are unique regardless of case; unknown dates stay blank.

Each equipment record has four tabs:

- **Overview:** description, photo, identification/location, equipment notes,
  supplier contact details, purchase/commissioning/warranty dates, next service
  and calibration dates, plus additional labeled important dates.
- **Maintenance:** planned, in-progress, completed, or cancelled service, repair,
  inspection, and calibration records. Each has scheduled/completion dates,
  provider, work notes, and optional next due date. Existing records can be edited.
- **Vendor log:** dated emails, calls, meetings, service visits, portal contacts,
  quotes, orders, and support tickets entered as interaction records. Store the
  contact, reference, notes, follow-up date, and open/closed status.
- **Photos & documents:** upload equipment photos, manuals, quotations, or service
  reports. Files can be linked to an individual maintenance or vendor record.

Vendor interactions are a manually maintained log. There is no connected email
import or outgoing-message automation in this feature.

## Dates and status

Inventory filters find overdue items, items due today, and items due within 30
days. The next action date is the earliest of the equipment's service/calibration
date, an unfinished maintenance appointment, or an open vendor follow-up.
Completed/cancelled work and closed vendor follow-ups stop contributing their
appointment dates. Retired equipment is excluded from attention counts.

The Lab overview includes an Equipment card showing active items and how many
are due for action. Global Ctrl/Cmd+K search finds equipment by name, model,
serial number, asset tag, or vendor, with links back to its record. Inventory
search additionally covers descriptions, category, manufacturer, and location.

Completing a maintenance record requires an actual completion date. Its next due
date updates the equipment's service date (or calibration date for calibrations).
Completing work without another due date clears a corresponding already-due
master date. A backdated older service does not replace dates from newer completed
work; editing only its notes does not change the current schedule. Purchase,
warranty, and custom milestone dates remain historical/reference dates and do
not by themselves create overdue work. Dates do not generate emails, calendar
appointments, or task records automatically.

Use **Edit equipment** to retire an item while retaining its service/vendor
history. Existing experiment equipment text is preserved; this change does not
infer or rewrite equipment links in earlier experiments.

## Photos and documents

Supported photos: JPEG, PNG, WebP, and GIF, up to 10 MB and 40 megapixels. Photos
are verified from their contents, and thumbnails are generated without changing
the original file. PDF documents are checked with PyMuPDF and limited to 20 MB.
The gallery shows captions and related service/vendor records. **Remove
attachment** removes that file and its inventory attachment record.

Files are stored privately in
`$JFR_DATA_DIR/attachments/equipment/<equipment-id>/`, using generated filenames.
They are served through equipment-specific routes under the app's existing
private-access policy, with ownership/path checks. Documents download as PDFs;
photos can open in the browser. No public static upload directory is created.

## Storage and API

Five additive tables in the existing Journal-Fit database:
`equipment`, `equipment_maintenance`, `equipment_interaction`,
`equipment_milestone`, and `equipment_file`. App startup applies the schema
idempotently. Paper IDs, vector indexes, writing projects, and existing experiment
records are not changed. Inventory tables and the attachments folder should both
be included in backups.

- `GET /api/equipment?q=&status=&due=&limit=50&offset=0`: inventory and summary.
  `due` accepts `now`, `overdue`, or `soon`.
- `POST /api/equipment`: create equipment.
- `GET /api/equipment/{id}`: full equipment/history/file metadata.
- `PATCH /api/equipment/{id}`: partial equipment updates.
- `POST /api/equipment/{id}/records/{kind}`: add a `maintenance`, `interaction`,
  or `milestone` record.
- `PATCH /api/equipment/{id}/records/{kind}/{record-id}`: update that record.
- `POST /api/equipment/{id}/files`: multipart upload (`file`, optional `caption`
  and `related`, such as `maintenance:<record-id>`).
- `GET /equipment/{id}/files/{file-id}`: private original; add `?thumbnail=true`
  for a small JPEG preview of a photo.

The native HTML forms support creating/editing records and uploading files
without JavaScript. The responsive layout uses tabs and collapsible forms to
keep the equipment workspace compact.

## Checks and activation

```bash
PYTHONPATH=.:submission_strategy:tests submission_strategy/.venv/bin/python \
  -c 'import uvloop, unittest; uvloop.install(); unittest.main(module="test_equipment", verbosity=2)'
```

The existing environment already includes the image/PDF dependencies. They are
declared in the runtime requirements and checked by `tools/check_runtime.py`.
Load the new routes in an already running app with:

```bash
systemctl --user restart labui
```

Reload the browser, then select **Lab → Equipment inventory → Add equipment**.
