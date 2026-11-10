"""Inventory history, due dates, file ownership, and complete native form flows."""

import io
import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jfr import equipment
from jfr.config import Settings
from jfr.db.schema import DDL, init_db
from jfr.web import equipment_routes, workspace_routes
from jfr.web.private_access import PrivateAccessMiddleware
from jfr.web.workspaces import workspace_for_path
from PIL import Image


class InventoryFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "lab.sqlite"
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)
        self.settings = Settings(
            data_dir=self.root,
            db_path=self.db,
            attachments_dir=self.root / "attachments",
        )
        p = patch.object(equipment_routes, "get_settings", return_value=self.settings)
        p.start()
        self.addCleanup(p.stop)
        self.app = FastAPI()
        self.app.include_router(equipment_routes.router)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.today = date.today().isoformat()
        self.past = (date.today() - timedelta(days=5)).isoformat()
        self.future = (date.today() + timedelta(days=90)).isoformat()

    def item(self, **values):
        return equipment.save_equipment(
            self.conn,
            {
                "name": "Nanoparticle tracking analyzer",
                "model": "NS300",
                "asset_tag": "NTA-01",
                **values,
            },
        )

    def maintenance(self, equipment_id, **values):
        return equipment.save_record(
            self.conn,
            equipment_id,
            "maintenance",
            {"title": "Annual service", "scheduled_for": self.today, **values},
        )

    @staticmethod
    def photo():
        data = io.BytesIO()
        Image.new("RGB", (900, 700), "teal").save(data, format="PNG")
        return data.getvalue()

    @staticmethod
    def pdf():
        import pymupdf

        with pymupdf.open() as document:
            document.new_page().insert_text((40, 60), "Equipment service report")
            return document.tobytes()


class InventoryDataTests(InventoryFixture):
    def test_inventory_is_an_additive_schema_change(self):
        legacy = self.root / "legacy.sqlite"
        with sqlite3.connect(legacy) as conn:
            conn.executescript(DDL.replace(equipment.DDL, ""))
            conn.execute(
                "INSERT INTO experiment(id,name,equipment) VALUES('existing','Existing experiment','Existing free-text equipment')"
            )
            before = conn.execute("SELECT * FROM experiment").fetchall()
        upgraded = init_db(legacy)
        self.addCleanup(upgraded.close)
        self.assertEqual(
            [tuple(row) for row in upgraded.execute("SELECT * FROM experiment")], before
        )
        self.assertEqual(equipment.list_equipment(upgraded)["total"], 0)

    def test_description_vendor_dates_and_partial_updates_round_trip(self):
        item = self.item(
            description="Measures bubble size distributions.",
            location="Room 201",
            owner="Lab manager",
            purchased_on="2022-03-04",
            vendor_name="Instrument vendor",
            vendor_email="support@example.com",
            vendor_url="https://example.com",
        )
        updated = equipment.save_equipment(
            self.conn, {"status": "maintenance"}, item["id"]
        )
        self.assertEqual(updated["description"], item["description"])
        self.assertEqual(updated["purchased_on"], "2022-03-04")
        self.assertEqual(updated["vendor_email"], "support@example.com")
        self.assertEqual(equipment.detail(self.conn, item["id"])["maintenance"], [])

    def test_invalid_data_and_duplicate_asset_tags_are_atomic(self):
        item = self.item()
        for changes in [
            {"name": ""},
            {"purchased_on": "2026-02-30"},
            {"status": "broken-value"},
            {"vendor_url": "javascript:alert(1)"},
            {"vendor_email": "not-email"},
        ]:
            with (
                self.subTest(changes=changes),
                self.assertRaises(equipment.EquipmentError),
            ):
                equipment.save_equipment(self.conn, changes, item["id"])
            self.assertEqual(
                equipment.require(self.conn, item["id"])["name"], item["name"]
            )
        with self.assertRaises(equipment.EquipmentError):
            self.item(name="Second instrument", asset_tag="nta-01")
        self.assertEqual(equipment.list_equipment(self.conn)["total"], 1)

    def test_dates_and_service_followups_drive_due_filters_and_lab_overview(self):
        first = self.item(next_maintenance_on=self.past)
        second = self.item(name="Pump", asset_tag="P-1", calibration_due_on=self.today)
        retired = self.item(
            name="Retired pump",
            asset_tag="P-2",
            status="retired",
            next_maintenance_on=self.past,
        )
        self.assertEqual(equipment.summary(self.conn)["attention"], 2)
        self.assertEqual(equipment.list_equipment(self.conn, due="overdue")["total"], 1)
        self.assertEqual(equipment.list_equipment(self.conn, due="now")["total"], 2)
        self.assertEqual(
            equipment.list_equipment(self.conn, status="retired")["items"][0]["id"],
            retired["id"],
        )
        data = workspace_routes.lab_overview(self.db)
        self.assertEqual((data["equipment_count"], data["equipment_attention"]), (2, 2))
        equipment.save_equipment(self.conn, {"next_maintenance_on": None}, first["id"])
        equipment.save_record(
            self.conn,
            first["id"],
            "interaction",
            {
                "subject": "Quote follow-up",
                "occurred_on": self.past,
                "follow_up_on": self.today,
            },
        )
        self.assertEqual(equipment.list_equipment(self.conn, due="now")["total"], 2)
        self.assertNotEqual(first["id"], second["id"])

    def test_completing_service_updates_next_date_and_keeps_calibration_separate(self):
        item = self.item(next_maintenance_on=self.past, calibration_due_on=self.past)
        service = self.maintenance(item["id"], scheduled_for=self.past)
        equipment.save_record(
            self.conn,
            item["id"],
            "maintenance",
            {
                "status": "completed",
                "completed_on": self.today,
                "next_due_on": self.future,
            },
            service["id"],
        )
        current = equipment.require(self.conn, item["id"])
        self.assertEqual(current["next_maintenance_on"], self.future)
        self.assertEqual(current["calibration_due_on"], self.past)
        self.maintenance(
            item["id"],
            title="Calibration",
            kind="calibration",
            status="completed",
            completed_on=self.today,
            next_due_on=self.future,
        )
        self.assertEqual(equipment.summary(self.conn)["attention"], 0)

    def test_completed_work_requires_actual_date_and_next_due_is_after_completion(self):
        item = self.item()
        for changes in [
            {"status": "completed"},
            {"status": "completed", "completed_on": self.future},
            {"status": "planned", "completed_on": self.today},
            {
                "status": "completed",
                "completed_on": self.today,
                "next_due_on": self.past,
            },
        ]:
            with (
                self.subTest(changes=changes),
                self.assertRaises(equipment.EquipmentError),
            ):
                self.maintenance(item["id"], **changes)
        self.assertEqual(equipment.detail(self.conn, item["id"])["maintenance"], [])

    def test_old_service_backfills_and_note_edits_do_not_regress_next_due_date(self):
        item = self.item()
        current = self.maintenance(
            item["id"],
            status="completed",
            completed_on=self.today,
            next_due_on=self.future,
        )
        self.maintenance(
            item["id"],
            title="Older service",
            scheduled_for=self.past,
            status="completed",
            completed_on=self.past,
            next_due_on=self.today,
        )
        equipment.save_equipment(
            self.conn,
            {"next_maintenance_on": (date.today() + timedelta(days=120)).isoformat()},
            item["id"],
        )
        equipment.save_record(
            self.conn,
            item["id"],
            "maintenance",
            {"notes": "Corrected service notes"},
            current["id"],
        )
        self.assertEqual(
            equipment.require(self.conn, item["id"])["next_maintenance_on"],
            (date.today() + timedelta(days=120)).isoformat(),
        )

    def test_vendor_followups_can_close_without_deleting_history(self):
        item = self.item()
        interaction = equipment.save_record(
            self.conn,
            item["id"],
            "interaction",
            {
                "subject": "Replacement laser quotation",
                "occurred_on": self.past,
                "channel": "email",
                "contact": "Vendor support",
                "reference": "Ticket 123",
                "notes": "Asked for price and delivery date.",
                "follow_up_on": self.today,
            },
        )
        self.assertEqual(equipment.summary(self.conn)["attention"], 1)
        equipment.save_record(
            self.conn,
            item["id"],
            "interaction",
            {"status": "closed"},
            interaction["id"],
        )
        self.assertEqual(equipment.summary(self.conn)["attention"], 0)
        self.assertEqual(
            equipment.detail(self.conn, item["id"])["interactions"][0]["reference"],
            "Ticket 123",
        )

    def test_custom_dates_are_editable_and_visible_with_core_dates(self):
        item = self.item(purchased_on="2020-01-01")
        milestone = equipment.save_record(
            self.conn,
            item["id"],
            "milestone",
            {
                "title": "Safety inspection",
                "occurs_on": self.future,
                "notes": "Annual inspection",
            },
        )
        equipment.save_record(
            self.conn,
            item["id"],
            "milestone",
            {"title": "Inspection appointment"},
            milestone["id"],
        )
        dates = equipment.detail(self.conn, item["id"])["dates"]
        self.assertEqual(
            [entry["title"] for entry in dates], ["Purchased", "Inspection appointment"]
        )

    def test_record_updates_cannot_cross_equipment_boundaries(self):
        first = self.item()
        second = self.item(asset_tag="TWO")
        service = self.maintenance(first["id"])
        with self.assertRaises(equipment.EquipmentNotFound):
            equipment.save_record(
                self.conn,
                second["id"],
                "maintenance",
                {"notes": "Wrong parent"},
                service["id"],
            )

    def test_inventory_search_is_literal_and_pagination_is_stable(self):
        self.item(name="Pump A_1%", asset_tag="ONE")
        self.item(name="Pump AB10", asset_tag="TWO")
        self.assertEqual(equipment.list_equipment(self.conn, q="A_1%")["total"], 1)
        page = equipment.list_equipment(self.conn, q="Pump", limit=1)
        other = equipment.list_equipment(self.conn, q="Pump", limit=1, offset=1)
        self.assertEqual(page["total"], 2)
        self.assertNotEqual(page["items"][0]["id"], other["items"][0]["id"])


class InventoryWebTests(InventoryFixture):
    def test_full_create_edit_and_detail_form_workflow(self):
        response = self.client.get("/equipment")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Start your equipment inventory", response.text)
        self.assertEqual(self.client.get("/equipment/new").status_code, 200)
        created = self.client.post(
            "/equipment",
            data={
                "name": "Zeta potential analyzer",
                "asset_tag": "Z-1",
                "description": "Electrophoretic measurements.",
            },
            follow_redirects=False,
        )
        self.assertEqual(created.status_code, 303, created.text)
        url = created.headers["location"]
        item_id = url.rsplit("/", 1)[1]
        html = self.client.get(url).text
        self.assertIn('data-workspace="lab"', html)
        self.assertIn("Electrophoretic measurements.", html)
        edited = self.client.post(
            url + "/edit",
            data={"name": "Zeta analyzer", "location": "Room 101"},
            follow_redirects=False,
        )
        self.assertEqual(edited.status_code, 303)
        self.assertEqual(
            self.client.get("/api/equipment/" + item_id).json()["location"], "Room 101"
        )
        for tab in ["overview", "maintenance", "interaction", "files"]:
            self.assertEqual(self.client.get(url + "?tab=" + tab).status_code, 200)

    def test_validation_preserves_form_values_and_escapes_source_text(self):
        response = self.client.post(
            "/equipment",
            data={"name": "<script>alert(1)</script>", "purchased_on": "invalid"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertNotIn("<script>alert(1)</script>", response.text)
        item = self.item(name="<script>alert(1)</script>")
        for url in ["/equipment", "/equipment/" + item["id"]]:
            response = self.client.get(url)
            self.assertIn("&lt;script&gt;", response.text)
            self.assertNotIn("<script>alert(1)</script>", response.text)

    def test_maintenance_and_vendor_forms_support_edits_and_inline_errors(self):
        item = self.item()
        base = "/equipment/" + item["id"]
        failed = self.client.post(
            base + "/records/maintenance",
            data={
                "title": "Annual service",
                "scheduled_for": self.today,
                "status": "completed",
            },
        )
        self.assertEqual(failed.status_code, 422)
        self.assertIn("needs a completion date", failed.text)
        saved = self.client.post(
            base + "/records/maintenance",
            data={"title": "Annual service", "scheduled_for": self.today},
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 303)
        service = equipment.detail(self.conn, item["id"])["maintenance"][0]
        edit = self.client.post(
            base + "/records/maintenance/" + service["id"],
            data={
                "title": "Completed service",
                "scheduled_for": self.today,
                "status": "completed",
                "completed_on": self.today,
            },
            follow_redirects=False,
        )
        self.assertEqual(edit.status_code, 303)
        self.assertIn(
            "Completed service", self.client.get(base + "?tab=maintenance").text
        )
        vendor = self.client.post(
            base + "/records/interaction",
            data={
                "subject": "Quote request",
                "occurred_on": self.today,
                "channel": "phone",
            },
            follow_redirects=False,
        )
        self.assertEqual(vendor.status_code, 303)
        self.assertIn("Quote request", self.client.get(base + "?tab=interaction").text)

    def test_api_partial_updates_unknown_fields_and_not_found(self):
        created = self.client.post(
            "/api/equipment", json={"name": "Pressure pump", "serial_number": "ABC-100"}
        )
        self.assertEqual(created.status_code, 201)
        item = created.json()
        updated = self.client.patch(
            "/api/equipment/" + item["id"], json={"status": "out_of_service"}
        )
        self.assertEqual(updated.json()["serial_number"], "ABC-100")
        self.assertEqual(
            self.client.patch(
                "/api/equipment/" + item["id"], json={"unknown": "value"}
            ).status_code,
            422,
        )
        self.assertEqual(self.client.get("/equipment/missing").status_code, 404)
        self.assertEqual(self.client.get("/api/equipment?offset=-1").status_code, 422)

    def test_photo_upload_thumbnail_download_and_removal(self):
        item = self.item()
        data = self.photo()
        response = self.client.post(
            "/api/equipment/" + item["id"] + "/files",
            files={"file": ("../instrument.png", data, "application/octet-stream")},
            data={"caption": "Front panel"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        file = response.json()
        url = "/equipment/" + item["id"] + "/files/" + file["id"]
        full = self.client.get(url)
        self.assertEqual(full.content, data)
        self.assertEqual(full.headers["content-type"], "image/png")
        self.assertIn("inline", full.headers["content-disposition"])
        thumb = self.client.get(url + "?thumbnail=true")
        with Image.open(io.BytesIO(thumb.content)) as image:
            self.assertLessEqual(image.width, 600)
            self.assertLessEqual(image.height, 400)
        html = self.client.get("/equipment/" + item["id"] + "?tab=files").text
        self.assertIn("Front panel", html)
        path = (
            self.settings.attachments_dir
            / "equipment"
            / item["id"]
            / file["stored_name"]
        )
        self.assertTrue(path.exists())
        self.assertEqual(
            self.client.post(url + "/remove", follow_redirects=False).status_code, 303
        )
        self.assertFalse(path.exists())
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_pdf_can_be_attached_to_vendor_interaction(self):
        item = self.item()
        record = equipment.save_record(
            self.conn,
            item["id"],
            "interaction",
            {"subject": "Service quote", "occurred_on": self.today},
        )
        response = self.client.post(
            "/equipment/" + item["id"] + "/files",
            files={"file": ("quote.pdf", self.pdf(), "application/pdf")},
            data={"related": "interaction:" + record["id"]},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)
        file = equipment.detail(self.conn, item["id"])["files"][0]
        download = self.client.get("/equipment/" + item["id"] + "/files/" + file["id"])
        self.assertEqual(download.headers["content-type"], "application/pdf")
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertIn(
            "quote.pdf",
            self.client.get("/equipment/" + item["id"] + "?tab=interaction").text,
        )

    def test_upload_rejects_invalid_files_oversize_photos_and_wrong_parent(self):
        first = self.item()
        second = self.item(asset_tag="SECOND")
        service = self.maintenance(second["id"])
        url = "/api/equipment/" + first["id"] + "/files"
        for payload in [
            b"<svg><script>alert(1)</script></svg>",
            b"%PDF-not-a-document",
            b"",
        ]:
            response = self.client.post(
                url, files={"file": ("file.png", payload, "image/png")}
            )
            self.assertEqual(response.status_code, 422, response.text)
        with patch.object(equipment, "MAX_PHOTO", 10):
            self.assertEqual(
                self.client.post(
                    url, files={"file": ("file.png", self.photo(), "image/png")}
                ).status_code,
                422,
            )
        self.assertEqual(
            self.client.post(
                url,
                files={"file": ("file.png", self.photo(), "image/png")},
                data={"related": "maintenance:" + service["id"]},
            ).status_code,
            422,
        )
        self.assertEqual(equipment.detail(self.conn, first["id"])["files"], [])

    def test_attachment_ids_do_not_allow_cross_parent_access_or_path_escape(self):
        first = self.item()
        second = self.item(asset_tag="SECOND")
        file = equipment.save_file(
            self.conn,
            self.settings.attachments_dir / "equipment",
            first["id"],
            self.photo(),
            "photo.png",
        )
        self.assertEqual(
            self.client.get(
                "/equipment/" + second["id"] + "/files/" + file["id"]
            ).status_code,
            404,
        )
        with self.conn:
            self.conn.execute(
                "UPDATE equipment_file SET stored_name=? WHERE id=?",
                ("../../outside.png", file["id"]),
            )
        self.assertEqual(
            self.client.get(
                "/equipment/" + first["id"] + "/files/" + file["id"]
            ).status_code,
            404,
        )

    def test_inventory_uses_the_existing_private_access_boundary(self):
        policy = self.root / "access.json"
        policy.write_text(json.dumps({"owner_login": "owner@example.com"}))
        app = FastAPI()
        app.include_router(equipment_routes.router)
        app.add_middleware(PrivateAccessMiddleware, policy_path=policy)
        client = TestClient(app, client=("100.64.1.2", 12345))
        self.addCleanup(client.close)
        self.assertEqual(client.get("/equipment").status_code, 403)
        self.assertEqual(
            client.get(
                "/equipment", headers={"Tailscale-User-Login": "owner@example.com"}
            ).status_code,
            200,
        )

    def test_equipment_belongs_to_lab_and_is_available_to_global_search(self):
        item = self.item()
        self.assertEqual(workspace_for_path("/equipment/" + item["id"])["id"], "lab")
        paths = {
            name: self.root / (name + ".sqlite")
            for name in ["papers", "memory", "writing"]
        }
        with (
            patch.object(workspace_routes, "get_settings", return_value=self.settings),
            patch.object(workspace_routes, "research_paths", return_value=paths),
        ):
            matches = workspace_routes.search_workspaces("NS300")
        self.assertEqual(matches[0]["href"], "/equipment/" + item["id"])


if __name__ == "__main__":
    unittest.main()
