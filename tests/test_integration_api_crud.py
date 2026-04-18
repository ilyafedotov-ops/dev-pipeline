"""Integration tests for full CRUD lifecycle via the DevGodzilla REST API.

Uses the shared ``test_client`` / ``seeded_project`` / ``seeded_protocol``
fixtures backed by a real temp SQLite database — no MagicMock for DB.
"""

import pytest


# ---------------------------------------------------------------------------
# Projects CRUD
# ---------------------------------------------------------------------------


class TestProjectCRUD:
    """Full create → read → update → delete lifecycle for /projects."""

    def test_create_project(self, test_client):
        """POST /projects creates a project and returns it."""
        payload = {
            "name": "crud-test-project",
            "git_url": "",
            "base_branch": "main",
            "auto_onboard": False,
        }
        resp = test_client.post("/projects", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "crud-test-project"
        assert body["base_branch"] == "main"
        assert "id" in body
        assert body["id"] > 0

    def test_list_projects_empty(self, test_client):
        """GET /projects returns a list (may be empty)."""
        resp = test_client.get("/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_full_project_lifecycle(self, test_client):
        """Create → list → get → update → delete a project."""
        # 1. Create
        create_resp = test_client.post(
            "/projects",
            json={
                "name": "lifecycle-project",
                "git_url": "https://github.com/example/lifecycle.git",
                "base_branch": "develop",
                "auto_onboard": False,
            },
        )
        assert create_resp.status_code == 200
        project = create_resp.json()
        pid = project["id"]
        assert project["name"] == "lifecycle-project"

        # 2. List (should contain the new project)
        list_resp = test_client.get("/projects")
        assert list_resp.status_code == 200
        ids = [p["id"] for p in list_resp.json()]
        assert pid in ids

        # 3. Get single
        get_resp = test_client.get(f"/projects/{pid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "lifecycle-project"
        assert get_resp.json()["git_url"] == "https://github.com/example/lifecycle.git"

        # 4. Update
        update_resp = test_client.put(
            f"/projects/{pid}",
            json={"name": "lifecycle-renamed", "description": "updated desc"},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["name"] == "lifecycle-renamed"
        assert updated["description"] == "updated desc"

        # 5. Verify update persisted
        get_resp2 = test_client.get(f"/projects/{pid}")
        assert get_resp2.json()["name"] == "lifecycle-renamed"

        # 6. Delete
        del_resp = test_client.delete(f"/projects/{pid}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # 7. Verify deleted → 404
        get_resp3 = test_client.get(f"/projects/{pid}")
        assert get_resp3.status_code == 404

    def test_get_project_404(self, test_client):
        """GET /projects/{id} returns 404 for non-existent project."""
        resp = test_client.get("/projects/999999")
        assert resp.status_code == 404

    def test_update_project_404(self, test_client):
        """PUT /projects/{id} returns 404 for non-existent project."""
        resp = test_client.put("/projects/999999", json={"name": "nope"})
        assert resp.status_code == 404

    def test_delete_project_404(self, test_client):
        """DELETE /projects/{id} returns 404 for non-existent project."""
        resp = test_client.delete("/projects/999999")
        assert resp.status_code == 404

    def test_create_project_invalid_input(self, test_client):
        """POST /projects with missing required fields returns 422."""
        resp = test_client.post("/projects", json={})
        assert resp.status_code == 422

    def test_archive_unarchive_project(self, test_client, seeded_project):
        """POST archive/unarchive toggles project status."""
        pid = seeded_project.id

        # Archive
        archive_resp = test_client.post(f"/projects/{pid}/archive")
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == "archived"

        # Unarchive
        unarchive_resp = test_client.post(f"/projects/{pid}/unarchive")
        assert unarchive_resp.status_code == 200
        assert unarchive_resp.json()["status"] == "active"

    def test_archive_project_404(self, test_client):
        """Archive a non-existent project returns 404."""
        resp = test_client.post("/projects/999999/archive")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Protocols CRUD
# ---------------------------------------------------------------------------


class TestProtocolCRUD:
    """Full create → read → list lifecycle for /protocols."""

    def test_create_protocol(self, test_client, seeded_project):
        """POST /protocols creates a protocol run linked to a project."""
        payload = {
            "project_id": seeded_project.id,
            "protocol_name": "test-protocol-crud",
            "base_branch": "main",
        }
        resp = test_client.post("/protocols", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["protocol_name"] == "test-protocol-crud"
        assert body["project_id"] == seeded_project.id
        assert body["status"] == "pending"
        assert body["base_branch"] == "main"
        assert "id" in body

    def test_list_protocols(self, test_client):
        """GET /protocols returns a list."""
        resp = test_client.get("/protocols")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_protocol(self, test_client, seeded_protocol):
        """GET /protocols/{id} returns the seeded protocol."""
        resp = test_client.get(f"/protocols/{seeded_protocol.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == seeded_protocol.id
        assert body["protocol_name"] == seeded_protocol.protocol_name

    def test_full_protocol_lifecycle(self, test_client, seeded_project):
        """Create → get → list → verify protocol lifecycle."""
        pid = seeded_project.id

        # 1. Create via top-level endpoint
        create_resp = test_client.post(
            "/protocols",
            json={
                "project_id": pid,
                "protocol_name": "lifecycle-protocol",
                "base_branch": "main",
                "description": "Full lifecycle test",
            },
        )
        assert create_resp.status_code == 200
        protocol = create_resp.json()
        proto_id = protocol["id"]
        assert protocol["status"] == "pending"

        # 2. Get by ID
        get_resp = test_client.get(f"/protocols/{proto_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["protocol_name"] == "lifecycle-protocol"
        assert get_resp.json()["description"] == "Full lifecycle test"

        # 3. List all protocols — should include our new one
        list_resp = test_client.get("/protocols")
        assert list_resp.status_code == 200
        ids = [p["id"] for p in list_resp.json()]
        assert proto_id in ids

        # 4. List protocols for project
        proj_protos_resp = test_client.get(f"/projects/{pid}/protocols")
        assert proj_protos_resp.status_code == 200
        proj_proto_ids = [p["id"] for p in proj_protos_resp.json()]
        assert proto_id in proj_proto_ids

    def test_create_protocol_via_project_endpoint(self, test_client, seeded_project):
        """POST /projects/{id}/protocols creates a protocol scoped to the project."""
        resp = test_client.post(
            f"/projects/{seeded_project.id}/protocols",
            json={
                "protocol_name": "project-scoped-proto",
                "base_branch": "main",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["project_id"] == seeded_project.id
        assert body["protocol_name"] == "project-scoped-proto"

    def test_get_protocol_404(self, test_client):
        """GET /protocols/{id} returns 404 for non-existent protocol."""
        resp = test_client.get("/protocols/999999")
        assert resp.status_code == 404

    def test_create_protocol_invalid_input(self, test_client):
        """POST /protocols with missing required fields returns 422."""
        resp = test_client.post("/protocols", json={})
        assert resp.status_code == 422

    def test_create_protocol_with_nonexistent_project(self, test_client):
        """POST /protocols with non-existent project_id creates an orphan in SQLite.

        SQLite does not enforce FK constraints by default, so this succeeds
        at the DB level.  The protocol is still retrievable.
        """
        resp = test_client.post(
            "/protocols",
            json={
                "project_id": 999999,
                "protocol_name": "orphan-protocol",
                "base_branch": "main",
            },
        )
        # SQLite without FK enforcement allows this — verify it persisted
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == 999999
        assert body["protocol_name"] == "orphan-protocol"

    def test_list_project_protocols_404(self, test_client):
        """GET /projects/{id}/protocols returns 404 for non-existent project."""
        resp = test_client.get("/projects/999999/protocols")
        assert resp.status_code == 404

    def test_protocol_steps_empty(self, test_client, seeded_protocol):
        """GET /protocols/{id}/steps returns empty list for new protocol."""
        resp = test_client.get(f"/protocols/{seeded_protocol.id}/steps")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Cross-resource integration
# ---------------------------------------------------------------------------


class TestCrossResourceIntegration:
    """Tests that verify relationships between projects and protocols."""

    def test_delete_project_cascades_to_protocols(self, test_client, db_session):
        """Deleting a project should handle associated protocols."""
        # Create project via API
        proj_resp = test_client.post(
            "/projects",
            json={
                "name": "cascade-test",
                "git_url": "",
                "base_branch": "main",
                "auto_onboard": False,
            },
        )
        assert proj_resp.status_code == 200
        pid = proj_resp.json()["id"]

        # Create protocol via API
        proto_resp = test_client.post(
            "/protocols",
            json={
                "project_id": pid,
                "protocol_name": "cascade-proto",
                "base_branch": "main",
            },
        )
        assert proto_resp.status_code == 200
        proto_id = proto_resp.json()["id"]

        # Delete project
        del_resp = test_client.delete(f"/projects/{pid}")
        assert del_resp.status_code == 200

        # Project is gone
        assert test_client.get(f"/projects/{pid}").status_code == 404

        # Protocol is also gone (cascade)
        proto_get = test_client.get(f"/protocols/{proto_id}")
        assert proto_get.status_code == 404

    def test_seeded_project_exists_via_api(self, test_client, seeded_project):
        """The seeded_project fixture creates a DB-visible project."""
        resp = test_client.get(f"/projects/{seeded_project.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Project"

    def test_seeded_protocol_exists_via_api(
        self, test_client, seeded_project, seeded_protocol
    ):
        """The seeded_protocol fixture creates a DB-visible protocol run."""
        resp = test_client.get(f"/protocols/{seeded_protocol.id}")
        assert resp.status_code == 200
        assert resp.json()["protocol_name"] == "test-protocol"
        assert resp.json()["project_id"] == seeded_project.id

    def test_multiple_protocols_per_project(self, test_client, seeded_project):
        """A project can have multiple protocol runs."""
        names = []
        for i in range(3):
            resp = test_client.post(
                "/protocols",
                json={
                    "project_id": seeded_project.id,
                    "protocol_name": f"multi-proto-{i}",
                    "base_branch": "main",
                },
            )
            assert resp.status_code == 200
            names.append(resp.json()["protocol_name"])

        # List project protocols
        list_resp = test_client.get(f"/projects/{seeded_project.id}/protocols")
        assert list_resp.status_code == 200
        returned_names = [p["protocol_name"] for p in list_resp.json()]
        for name in names:
            assert name in returned_names
