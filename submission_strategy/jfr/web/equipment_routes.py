"""Lab inventory pages and API. Files are served through private app routes."""

import io
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict

from jfr import equipment as inventory
from jfr.config import get_settings
from jfr.db import get_conn
from jfr.web.templating import make_templates

router = APIRouter()
templates = make_templates()
templates.env.globals.update(
    equipment_statuses=inventory.STATUSES,
    maintenance_kinds=inventory.MAINTENANCE_KINDS,
    maintenance_statuses=inventory.MAINTENANCE_STATUSES,
    contact_channels=inventory.CHANNELS,
    equipment_date_fields=inventory.DATE_FIELDS,
)
TABS = {
    "overview": "Overview",
    "maintenance": "Maintenance",
    "interaction": "Vendor log",
    "files": "Photos & documents",
}


class EquipmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = ""
    description: str = ""
    category: str = ""
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    asset_tag: str | None = None
    location: str = ""
    owner: str = ""
    status: str = "operational"
    purchased_on: str | None = None
    commissioned_on: str | None = None
    warranty_until: str | None = None
    calibration_due_on: str | None = None
    next_maintenance_on: str | None = None
    vendor_name: str = ""
    vendor_contact: str = ""
    vendor_email: str = ""
    vendor_phone: str = ""
    vendor_url: str = ""
    notes: str = ""


@contextmanager
def connection():
    conn = get_conn(get_settings().db_path)
    try:
        yield conn
    except inventory.EquipmentNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except inventory.EquipmentError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        conn.close()


def file_root():
    return get_settings().attachments_dir / "equipment"


def detail_page(
    request,
    conn,
    equipment_id,
    tab="overview",
    error=None,
    failed_record=None,
    failed_kind=None,
):
    equipment = inventory.detail(conn, equipment_id)
    titles = {record["id"]: record["title"] for record in equipment["maintenance"]}
    titles.update(
        {record["id"]: record["subject"] for record in equipment["interactions"]}
    )
    for file in equipment["files"]:
        file["related_title"] = titles.get(
            file["maintenance_id"] or file["interaction_id"]
        )
    return templates.TemplateResponse(
        request,
        "equipment_detail.html",
        {
            "equipment": equipment,
            "tab": tab if tab in TABS else "overview",
            "tabs": TABS,
            "error": error,
            "failed_record": failed_record,
            "failed_kind": failed_kind,
        },
        status_code=422 if error else 200,
    )


@router.get("/equipment")
def equipment_list(
    request: Request,
    q: str = Query("", max_length=200),
    status: str = "",
    due: str = "",
    offset: int = Query(0, ge=0),
):
    with connection() as conn:
        data = inventory.list_equipment(
            conn, q=q, status=status, due=due, offset=offset
        )
    return templates.TemplateResponse(
        request,
        "equipment.html",
        {"inventory": data, "q": q, "status": status, "due": due},
    )


@router.get("/equipment/new")
def new_equipment(request: Request):
    return templates.TemplateResponse(
        request,
        "equipment_form.html",
        {"equipment": {"status": "operational"}, "editing": False, "error": None},
    )


@router.post("/equipment")
async def equipment_create_form(request: Request):
    values = dict(await request.form())
    with connection() as conn:
        try:
            record = inventory.save_equipment(conn, values)
        except inventory.EquipmentError as exc:
            return templates.TemplateResponse(
                request,
                "equipment_form.html",
                {"equipment": values, "editing": False, "error": str(exc)},
                status_code=422,
            )
    return RedirectResponse("/equipment/" + record["id"], status_code=303)


@router.get("/equipment/{equipment_id}/edit")
def edit_equipment(request: Request, equipment_id: str):
    with connection() as conn:
        record = inventory.require(conn, equipment_id)
    return templates.TemplateResponse(
        request,
        "equipment_form.html",
        {"equipment": record, "editing": True, "error": None},
    )


@router.post("/equipment/{equipment_id}/edit")
async def equipment_update_form(request: Request, equipment_id: str):
    values = dict(await request.form())
    with connection() as conn:
        existing = inventory.require(conn, equipment_id)
        try:
            inventory.save_equipment(conn, values, equipment_id)
        except inventory.EquipmentError as exc:
            return templates.TemplateResponse(
                request,
                "equipment_form.html",
                {
                    "equipment": {**existing, **values},
                    "editing": True,
                    "error": str(exc),
                },
                status_code=422,
            )
    return RedirectResponse("/equipment/" + equipment_id, status_code=303)


@router.get("/equipment/{equipment_id}")
def equipment_detail(request: Request, equipment_id: str, tab: str = "overview"):
    with connection() as conn:
        return detail_page(request, conn, equipment_id, tab)


@router.post("/equipment/{equipment_id}/records/{kind}")
@router.post("/equipment/{equipment_id}/records/{kind}/{record_id}")
async def record_form(
    request: Request, equipment_id: str, kind: str, record_id: str | None = None
):
    values = dict(await request.form())
    tab = kind if kind in {"maintenance", "interaction"} else "overview"
    with connection() as conn:
        inventory.require(conn, equipment_id)
        try:
            inventory.save_record(conn, equipment_id, kind, values, record_id)
        except inventory.EquipmentNotFound:
            raise
        except inventory.EquipmentError as exc:
            return detail_page(
                request,
                conn,
                equipment_id,
                tab,
                str(exc),
                {**values, "id": record_id},
                kind,
            )
    return RedirectResponse(
        "/equipment/" + equipment_id + "?tab=" + tab, status_code=303
    )


async def upload(request, conn, equipment_id):
    form = await request.form(
        max_files=1, max_fields=4, max_part_size=inventory.MAX_DOCUMENT + 1024
    )
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise inventory.EquipmentError("Choose a photo or PDF to upload.")
    try:
        data = await file.read(inventory.MAX_DOCUMENT + 1)
        if len(data) > inventory.MAX_DOCUMENT:
            raise inventory.EquipmentError("Attachments must be 20 MB or smaller.")
        return inventory.save_file(
            conn,
            file_root(),
            equipment_id,
            data,
            file.filename or "",
            str(form.get("caption", "")),
            str(form.get("related", "")),
        )
    finally:
        await file.close()


@router.post("/equipment/{equipment_id}/files")
async def upload_form(request: Request, equipment_id: str):
    with connection() as conn:
        inventory.require(conn, equipment_id)
        try:
            await upload(request, conn, equipment_id)
        except inventory.EquipmentError as exc:
            return detail_page(request, conn, equipment_id, "files", str(exc))
    return RedirectResponse(
        "/equipment/" + equipment_id + "?tab=files", status_code=303
    )


@router.get("/equipment/{equipment_id}/files/{file_id}")
def get_file(equipment_id: str, file_id: str, thumbnail: bool = False):
    with connection() as conn:
        record, path = inventory.attachment(conn, file_root(), equipment_id, file_id)
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
    }
    if thumbnail and record["kind"] == "photo":
        from PIL import Image, ImageOps

        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)
            image.thumbnail((600, 400))
            if image.mode in {"RGBA", "LA", "P"}:
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=82)
        return Response(output.getvalue(), media_type="image/jpeg", headers=headers)
    return FileResponse(
        path,
        media_type=record["mime_type"],
        filename=record["original_name"],
        content_disposition_type="inline"
        if record["kind"] == "photo"
        else "attachment",
        headers=headers,
    )


@router.post("/equipment/{equipment_id}/files/{file_id}/remove")
def remove_file(equipment_id: str, file_id: str):
    with connection() as conn:
        _, path = inventory.attachment(conn, file_root(), equipment_id, file_id)
        with conn:
            conn.execute(
                "DELETE FROM equipment_file WHERE id=? AND equipment_id=?",
                (file_id, equipment_id),
            )
        path.unlink(missing_ok=True)
    return RedirectResponse(
        "/equipment/" + equipment_id + "?tab=files", status_code=303
    )


@router.get("/api/equipment")
def api_list(
    q: str = Query("", max_length=200),
    status: str = "",
    due: str = "",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    with connection() as conn:
        return inventory.list_equipment(
            conn, q=q, status=status, due=due, limit=limit, offset=offset
        )


@router.post("/api/equipment", status_code=201)
def api_create(body: EquipmentInput):
    with connection() as conn:
        return inventory.save_equipment(conn, body.model_dump(exclude_unset=True))


@router.get("/api/equipment/{equipment_id}")
def api_detail(equipment_id: str):
    with connection() as conn:
        return inventory.detail(conn, equipment_id)


@router.patch("/api/equipment/{equipment_id}")
def api_update(equipment_id: str, body: EquipmentInput):
    with connection() as conn:
        return inventory.save_equipment(
            conn, body.model_dump(exclude_unset=True), equipment_id
        )


@router.post("/api/equipment/{equipment_id}/records/{kind}", status_code=201)
def api_record(
    equipment_id: str, kind: str, values: Annotated[dict[str, str | None], Body()]
):
    with connection() as conn:
        return inventory.save_record(conn, equipment_id, kind, values)


@router.patch("/api/equipment/{equipment_id}/records/{kind}/{record_id}")
def api_record_update(
    equipment_id: str,
    kind: str,
    record_id: str,
    values: Annotated[dict[str, str | None], Body()],
):
    with connection() as conn:
        return inventory.save_record(conn, equipment_id, kind, values, record_id)


@router.post("/api/equipment/{equipment_id}/files", status_code=201)
async def api_upload(request: Request, equipment_id: str):
    with connection() as conn:
        inventory.require(conn, equipment_id)
        return await upload(request, conn, equipment_id)
