"""Equipment records, dated service history, vendor logs, and private files."""

from __future__ import annotations

import io
import re
import sqlite3
import uuid
import warnings
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

DDL = """
CREATE TABLE IF NOT EXISTS equipment (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 category TEXT NOT NULL DEFAULT '', manufacturer TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
 serial_number TEXT NOT NULL DEFAULT '', asset_tag TEXT COLLATE NOCASE UNIQUE,
 location TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'operational' CHECK(status IN ('operational','in_use','maintenance','out_of_service','retired')),
 purchased_on TEXT, commissioned_on TEXT, warranty_until TEXT, calibration_due_on TEXT, next_maintenance_on TEXT,
 vendor_name TEXT NOT NULL DEFAULT '', vendor_contact TEXT NOT NULL DEFAULT '', vendor_email TEXT NOT NULL DEFAULT '',
 vendor_phone TEXT NOT NULL DEFAULT '', vendor_url TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS equipment_status ON equipment(status);
CREATE TABLE IF NOT EXISTS equipment_maintenance (
 id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL REFERENCES equipment(id),
 title TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('service','repair','calibration','inspection')),
 scheduled_for TEXT NOT NULL, completed_on TEXT,
 status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','in_progress','completed','cancelled')),
 performed_by TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', next_due_on TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS equipment_maintenance_due ON equipment_maintenance(equipment_id,status,scheduled_for);
CREATE TABLE IF NOT EXISTS equipment_interaction (
 id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL REFERENCES equipment(id),
 occurred_on TEXT NOT NULL, subject TEXT NOT NULL,
 channel TEXT NOT NULL CHECK(channel IN ('email','phone','meeting','visit','portal','other')),
 contact TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '',
 follow_up_on TEXT, status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS equipment_interaction_due ON equipment_interaction(equipment_id,status,follow_up_on);
CREATE TABLE IF NOT EXISTS equipment_milestone (
 id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL REFERENCES equipment(id),
 title TEXT NOT NULL, occurs_on TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS equipment_file (
 id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL REFERENCES equipment(id),
 kind TEXT NOT NULL CHECK(kind IN ('photo','document')), original_name TEXT NOT NULL,
 stored_name TEXT NOT NULL UNIQUE, mime_type TEXT NOT NULL, byte_size INTEGER NOT NULL,
 caption TEXT NOT NULL DEFAULT '', maintenance_id TEXT REFERENCES equipment_maintenance(id),
 interaction_id TEXT REFERENCES equipment_interaction(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS equipment_file_parent ON equipment_file(equipment_id,created_at);
"""

STATUSES = {
    "operational": "Operational",
    "in_use": "In use",
    "maintenance": "Under maintenance",
    "out_of_service": "Out of service",
    "retired": "Retired",
}
MAINTENANCE_KINDS = {
    "service": "Service",
    "repair": "Repair",
    "calibration": "Calibration",
    "inspection": "Inspection",
}
MAINTENANCE_STATUSES = {
    "planned": "Planned",
    "in_progress": "In progress",
    "completed": "Completed",
    "cancelled": "Cancelled",
}
CHANNELS = {
    "email": "Email",
    "phone": "Phone",
    "meeting": "Meeting",
    "visit": "Service visit",
    "portal": "Vendor portal",
    "other": "Other",
}
DATE_FIELDS = {
    "purchased_on": "Purchased",
    "commissioned_on": "Commissioned",
    "warranty_until": "Warranty ends",
    "calibration_due_on": "Calibration due",
    "next_maintenance_on": "Maintenance due",
}
TEXT_FIELDS = {
    "name",
    "description",
    "category",
    "manufacturer",
    "model",
    "serial_number",
    "asset_tag",
    "location",
    "owner",
    "vendor_name",
    "vendor_contact",
    "vendor_email",
    "vendor_phone",
    "vendor_url",
    "notes",
}
MAX_PHOTO = 10 * 1024 * 1024
MAX_DOCUMENT = 20 * 1024 * 1024


class EquipmentError(ValueError):
    pass


class EquipmentNotFound(EquipmentError):
    pass


def now():
    return datetime.now(UTC).isoformat()


def text(value, label, *, required=False, maximum=300):
    value = str(value or "").strip()
    if required and not value:
        raise EquipmentError(f"{label} is required.")
    if len(value) > maximum:
        raise EquipmentError(f"{label} must be at most {maximum:,} characters.")
    return value


def day(value, label, *, required=False):
    value = text(value, label, required=required)
    if not value:
        return None
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError as exc:
        raise EquipmentError(f"{label} must be a valid date (YYYY-MM-DD).") from exc
    return value


def choice(value, allowed, label):
    if value not in allowed:
        raise EquipmentError(f"Choose a valid {label}.")
    return value


def require(conn, equipment_id):
    row = conn.execute("SELECT * FROM equipment WHERE id=?", (equipment_id,)).fetchone()
    if row is None:
        raise EquipmentNotFound("Equipment not found.")
    return dict(row)


def validate_equipment(values):
    data = {}
    for field in TEXT_FIELDS:
        maximum = 30000 if field in {"description", "notes"} else 300
        data[field] = text(
            values.get(field),
            field.replace("_", " ").capitalize(),
            required=field == "name",
            maximum=maximum,
        )
    data["asset_tag"] = data["asset_tag"] or None
    data["status"] = choice(
        values.get("status", "operational"), STATUSES, "equipment status"
    )
    for field, label in DATE_FIELDS.items():
        data[field] = day(values.get(field), label)
    if data["vendor_email"] and not re.fullmatch(
        r"[^\s@]+@[^\s@]+\.[^\s@]+", data["vendor_email"]
    ):
        raise EquipmentError("Enter a valid vendor email address.")
    if data["vendor_url"]:
        try:
            url = urlsplit(data["vendor_url"])
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
            ):
                raise ValueError
            _ = url.port
        except ValueError as exc:
            raise EquipmentError(
                "Vendor website must be an http or https URL without credentials."
            ) from exc
    return data


def save_equipment(conn, values, equipment_id=None):
    existing = require(conn, equipment_id) if equipment_id else {}
    data = validate_equipment({**existing, **values})
    timestamp = now()
    try:
        with conn:
            if existing:
                conn.execute(
                    "UPDATE equipment SET "
                    + ",".join(f"{key}=?" for key in data)
                    + ",updated_at=? WHERE id=?",
                    [*data.values(), timestamp, equipment_id],
                )
            else:
                equipment_id = uuid.uuid4().hex
                data.update(id=equipment_id, created_at=timestamp, updated_at=timestamp)
                conn.execute(
                    "INSERT INTO equipment ("
                    + ",".join(data)
                    + ") VALUES ("
                    + ",".join("?" for _ in data)
                    + ")",
                    list(data.values()),
                )
    except sqlite3.IntegrityError as exc:
        raise EquipmentError(
            "That asset tag is already assigned to another item."
        ) from exc
    return require(conn, equipment_id)


INVENTORY_QUERY = """SELECT e.*,
 (SELECT MIN(due_on) FROM (
   SELECT e.next_maintenance_on AS due_on UNION ALL SELECT e.calibration_due_on
   UNION ALL SELECT scheduled_for FROM equipment_maintenance WHERE equipment_id=e.id AND status IN ('planned','in_progress')
   UNION ALL SELECT follow_up_on FROM equipment_interaction WHERE equipment_id=e.id AND status='open'
 )) AS due_on,
 (SELECT id FROM equipment_file WHERE equipment_id=e.id AND kind='photo' ORDER BY created_at,id LIMIT 1) AS photo_id,
 (SELECT MAX(completed_on) FROM equipment_maintenance WHERE equipment_id=e.id AND status='completed') AS last_maintenance_on
 FROM equipment e"""


def summary(conn):
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='equipment'"
    ).fetchone():
        return {"total": 0, "active": 0, "attention": 0, "due_soon": 0}
    today = date.today()
    row = conn.execute(
        """WITH inventory AS ("""
        + INVENTORY_QUERY
        + """) SELECT count(*) AS total,
        COALESCE(SUM(status!='retired'),0) AS active,
        COALESCE(SUM(status!='retired' AND due_on<=?),0) AS attention,
        COALESCE(SUM(status!='retired' AND due_on<=?),0) AS due_soon FROM inventory""",
        (today.isoformat(), (today + timedelta(days=30)).isoformat()),
    ).fetchone()
    return dict(row)


def list_equipment(conn, *, q="", status="", due="", limit=50, offset=0):
    terms, params = [], []
    if q.strip():
        escaped = (
            q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        like = "%" + escaped + "%"
        fields = [
            "name",
            "description",
            "category",
            "manufacturer",
            "model",
            "serial_number",
            "asset_tag",
            "location",
            "vendor_name",
        ]
        terms.append(
            "(" + " OR ".join(f"{field} LIKE ? ESCAPE '\\'" for field in fields) + ")"
        )
        params.extend([like] * len(fields))
    if status:
        terms.append("status=?")
        params.append(choice(status, STATUSES, "equipment status"))
    if due:
        choice(due, {"now", "overdue", "soon"}, "date filter")
        terms.append(
            "status!='retired' AND due_on" + (" < ?" if due == "overdue" else " <= ?")
        )
        params.append(
            (
                date.today() + (timedelta(days=30) if due == "soon" else timedelta())
            ).isoformat()
        )
    where = " WHERE " + " AND ".join(terms) if terms else ""
    cte = "WITH inventory AS (" + INVENTORY_QUERY + ") "
    total = conn.execute(
        cte + "SELECT count(*) FROM inventory" + where, params
    ).fetchone()[0]
    records = [
        dict(row)
        for row in conn.execute(
            cte
            + "SELECT * FROM inventory"
            + where
            + " ORDER BY (status='retired'),name COLLATE NOCASE,id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
    ]
    for record in records:
        record["overdue"] = bool(
            record["due_on"]
            and record["due_on"] < date.today().isoformat()
            and record["status"] != "retired"
        )
    return {
        "items": records,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": summary(conn),
    }


def record_data(kind, values):
    if kind == "maintenance":
        data = {
            "title": text(values.get("title"), "Maintenance title", required=True),
            "kind": choice(
                values.get("kind", "service"), MAINTENANCE_KINDS, "maintenance type"
            ),
            "status": choice(
                values.get("status", "planned"),
                MAINTENANCE_STATUSES,
                "maintenance status",
            ),
            "scheduled_for": day(
                values.get("scheduled_for"), "Scheduled date", required=True
            ),
            "completed_on": day(values.get("completed_on"), "Completion date"),
            "performed_by": text(values.get("performed_by"), "Performed by"),
            "next_due_on": day(values.get("next_due_on"), "Next due date"),
        }
        if data["status"] == "completed":
            if not data["completed_on"]:
                raise EquipmentError("Completed maintenance needs a completion date.")
            if data["completed_on"] > date.today().isoformat():
                raise EquipmentError("A completion date cannot be in the future.")
        elif data["completed_on"]:
            raise EquipmentError(
                "Set the status to Completed to record a completion date."
            )
        if (
            data["next_due_on"]
            and data["completed_on"]
            and data["next_due_on"] <= data["completed_on"]
        ):
            raise EquipmentError("Next due date must be after the completion date.")
    elif kind == "interaction":
        data = {
            "subject": text(values.get("subject"), "Subject", required=True),
            "occurred_on": day(
                values.get("occurred_on"), "Interaction date", required=True
            ),
            "channel": choice(
                values.get("channel", "email"), CHANNELS, "contact channel"
            ),
            "contact": text(values.get("contact"), "Contact"),
            "reference": text(values.get("reference"), "Reference"),
            "follow_up_on": day(values.get("follow_up_on"), "Follow-up date"),
            "status": choice(
                values.get("status", "open"), {"open", "closed"}, "follow-up status"
            ),
        }
    elif kind == "milestone":
        data = {
            "title": text(values.get("title"), "Date label", required=True),
            "occurs_on": day(values.get("occurs_on"), "Important date", required=True),
        }
    else:
        raise EquipmentError("Unknown record type.")
    data["notes"] = text(values.get("notes"), "Notes", maximum=50000)
    return data


def save_record(conn, equipment_id, kind, values, record_id=None):
    require(conn, equipment_id)
    table = "equipment_" + choice(
        kind, {"maintenance", "interaction", "milestone"}, "record type"
    )
    existing = {}
    if record_id:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE id=? AND equipment_id=?",
            (record_id, equipment_id),
        ).fetchone()
        if row is None:
            raise EquipmentNotFound("Record not found for this equipment.")
        existing = dict(row)
    data = record_data(kind, {**existing, **values})
    timestamp = now()
    with conn:
        if existing:
            conn.execute(
                f"UPDATE {table} SET "
                + ",".join(f"{key}=?" for key in data)
                + ",updated_at=? WHERE id=?",
                [*data.values(), timestamp, record_id],
            )
        else:
            record_id = uuid.uuid4().hex
            data.update(
                id=record_id,
                equipment_id=equipment_id,
                created_at=timestamp,
                updated_at=timestamp,
            )
            conn.execute(
                f"INSERT INTO {table} ("
                + ",".join(data)
                + ") VALUES ("
                + ",".join("?" for _ in data)
                + ")",
                list(data.values()),
            )
        completion_changed = not existing or any(
            existing.get(key) != data.get(key)
            for key in ["status", "kind", "completed_on", "next_due_on"]
        )
        if (
            kind == "maintenance"
            and data["status"] == "completed"
            and completion_changed
        ):
            field = (
                "calibration_due_on"
                if data["kind"] == "calibration"
                else "next_maintenance_on"
            )
            previous = conn.execute(
                f"SELECT {field} FROM equipment WHERE id=?", (equipment_id,)
            ).fetchone()[0]
            comparison = (
                "kind='calibration'"
                if data["kind"] == "calibration"
                else "kind!='calibration'"
            )
            latest = conn.execute(
                "SELECT MAX(completed_on) FROM equipment_maintenance WHERE equipment_id=? AND status='completed' AND "
                + comparison,
                (equipment_id,),
            ).fetchone()[0]
            if data["completed_on"] == latest and (
                data["next_due_on"] or (previous and previous <= data["completed_on"])
            ):
                conn.execute(
                    f"UPDATE equipment SET {field}=?,updated_at=? WHERE id=?",
                    (data["next_due_on"], timestamp, equipment_id),
                )
        conn.execute(
            "UPDATE equipment SET updated_at=? WHERE id=?", (timestamp, equipment_id)
        )
    return dict(
        conn.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
    )


def detail(conn, equipment_id):
    equipment = require(conn, equipment_id)
    for kind, order in [
        ("maintenance", "scheduled_for"),
        ("interaction", "occurred_on"),
        ("milestone", "occurs_on"),
        ("file", "created_at"),
    ]:
        equipment[kind + "s" if kind != "maintenance" else "maintenance"] = [
            dict(row)
            for row in conn.execute(
                f"SELECT * FROM equipment_{kind} WHERE equipment_id=? ORDER BY {order} DESC,created_at DESC",
                (equipment_id,),
            )
        ]
    equipment["dates"] = [
        {"title": label, "date": equipment[field]}
        for field, label in DATE_FIELDS.items()
        if equipment[field]
    ]
    equipment["dates"].extend(
        {"title": item["title"], "date": item["occurs_on"], "notes": item["notes"]}
        for item in equipment["milestones"]
    )
    equipment["dates"].sort(key=lambda item: item["date"])
    return equipment


def validate_file(data, filename):
    name = filename.replace("\\", "/").split("/")[-1].strip()[:240] or "attachment"
    if not data:
        raise EquipmentError("Choose a nonempty photo or PDF.")
    if data.startswith(b"%PDF-"):
        if len(data) > MAX_DOCUMENT:
            raise EquipmentError("PDF files must be 20 MB or smaller.")
        import pymupdf

        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:
                if document.page_count < 1:
                    raise ValueError("Empty PDF")
        except (RuntimeError, ValueError) as exc:
            raise EquipmentError(
                "The PDF could not be read. Choose a valid PDF document."
            ) from exc
        return name, "document", "application/pdf", ".pdf"
    if len(data) > MAX_PHOTO:
        raise EquipmentError("Photos must be 10 MB or smaller.")
    from PIL import Image, UnidentifiedImageError

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                formats = {
                    "JPEG": ("image/jpeg", ".jpg"),
                    "PNG": ("image/png", ".png"),
                    "WEBP": ("image/webp", ".webp"),
                    "GIF": ("image/gif", ".gif"),
                }
                if (
                    image.format not in formats
                    or image.width * image.height > 40_000_000
                ):
                    raise EquipmentError(
                        "Use a JPEG, PNG, WebP, or GIF photo up to 40 megapixels."
                    )
                mime, extension = formats[image.format]
                image.verify()
            with Image.open(io.BytesIO(data)) as decoded:
                decoded.load()
    except EquipmentError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise EquipmentError("The file is not a valid photo or PDF.") from exc
    return name, "photo", mime, extension


def save_file(conn, root, equipment_id, data, filename, caption="", related=""):
    require(conn, equipment_id)
    name, kind, mime, extension = validate_file(data, filename)
    maintenance_id = interaction_id = None
    if related:
        parts = related.split(":", 1)
        if len(parts) != 2 or parts[0] not in {"maintenance", "interaction"}:
            raise EquipmentError("Choose a valid related record.")
        table, related_id = parts
        if not conn.execute(
            f"SELECT 1 FROM equipment_{table} WHERE id=? AND equipment_id=?",
            (related_id, equipment_id),
        ).fetchone():
            raise EquipmentError(
                "The related record belongs to different equipment or no longer exists."
            )
        if table == "maintenance":
            maintenance_id = related_id
        else:
            interaction_id = related_id
    caption = text(caption, "Caption", maximum=2000)
    file_id = uuid.uuid4().hex
    stored = file_id + extension
    directory = Path(root) / equipment_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / stored
    try:
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o600)
        with conn:
            conn.execute(
                """INSERT INTO equipment_file
                (id,equipment_id,kind,original_name,stored_name,mime_type,byte_size,caption,maintenance_id,interaction_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    file_id,
                    equipment_id,
                    kind,
                    name,
                    stored,
                    mime,
                    len(data),
                    caption,
                    maintenance_id,
                    interaction_id,
                    now(),
                ),
            )
            conn.execute(
                "UPDATE equipment SET updated_at=? WHERE id=?", (now(), equipment_id)
            )
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return dict(
        conn.execute("SELECT * FROM equipment_file WHERE id=?", (file_id,)).fetchone()
    )


def attachment(conn, root, equipment_id, file_id):
    require(conn, equipment_id)
    row = conn.execute(
        "SELECT * FROM equipment_file WHERE id=? AND equipment_id=?",
        (file_id, equipment_id),
    ).fetchone()
    if row is None:
        raise EquipmentNotFound("Attachment not found.")
    record = dict(row)
    directory = (Path(root) / equipment_id).resolve()
    path = (directory / record["stored_name"]).resolve()
    if (
        not path.is_relative_to(directory)
        or not directory.is_relative_to(Path(root).resolve())
        or not path.is_file()
    ):
        raise EquipmentNotFound("Attachment not found.")
    return record, path
