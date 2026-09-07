import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import AuditEvent, TruthStatus, TruthVersion
from app.seed import LEASEDESK_TRUTH


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([a-f0-9]+)"', html)
    assert match
    return match.group(1)


def test_full_draft_edit_approval_and_audit(authenticated_client: TestClient, app):
    truth_page = authenticated_client.get("/truth")
    csrf = csrf_from(truth_page.text)
    created = authenticated_client.post(
        "/truth/drafts", data={"csrf": csrf}, follow_redirects=False
    )
    assert created.status_code == 303
    edit_url = created.headers["location"]
    draft_id = edit_url.split("/")[3]

    form = {"csrf": csrf, "change_note": "Clarified the buyer evidence."}
    for key, item in LEASEDESK_TRUTH.model_dump(mode="json").items():
        form[f"{key}__value"] = item["value"]
        form[f"{key}__confidence"] = item["confidence"]
        form[f"{key}__basis"] = item["basis"]
    form["buyer__value"] = "The landlord or owner-operator accountable for the operation."

    saved = authenticated_client.post(
        f"/truth/drafts/{draft_id}", data=form, follow_redirects=False
    )
    assert saved.status_code == 303
    approved = authenticated_client.post(
        f"/truth/drafts/{draft_id}/approve",
        data={"csrf": csrf},
        follow_redirects=False,
    )
    assert approved.status_code == 303

    with app.state.session_factory() as db:
        versions = list(db.scalars(select(TruthVersion).order_by(TruthVersion.version)))
        assert [version.version for version in versions] == [1, 2]
        assert all(version.status == TruthStatus.APPROVED for version in versions)
        assert versions[0].content == LEASEDESK_TRUTH.model_dump(mode="json")
        assert versions[1].content["buyer"]["value"].startswith("The landlord")
        events = list(db.scalars(select(AuditEvent)))
        assert len(events) == 1
        assert events[0].event_type == "truth.approved"
        assert events[0].truth_version_id == draft_id


def test_approved_truth_is_immutable(authenticated_client: TestClient, app):
    with app.state.session_factory() as db:
        truth = db.scalar(select(TruthVersion).where(TruthVersion.version == 1))
        assert truth is not None
        truth.change_note = "Attempted mutation"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()


def test_invalid_draft_is_not_saved(authenticated_client: TestClient):
    page = authenticated_client.get("/truth")
    csrf = csrf_from(page.text)
    created = authenticated_client.post(
        "/truth/drafts", data={"csrf": csrf}, follow_redirects=False
    )
    draft_id = created.headers["location"].split("/")[3]
    response = authenticated_client.post(
        f"/truth/drafts/{draft_id}",
        data={"csrf": csrf, "change_note": "Invalid"},
    )
    assert response.status_code == 422
    assert "Revision not saved" in response.text


def test_post_without_csrf_is_rejected(authenticated_client: TestClient):
    response = authenticated_client.post("/truth/drafts", data={})
    assert response.status_code == 422
