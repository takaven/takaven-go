from fastapi.testclient import TestClient


def test_all_four_areas_exist(authenticated_client: TestClient):
    expected = {
        "/truth": "Product Truth",
        "/radar": "Attention Radar",
        "/creative": "Creative Engine",
        "/experiments": "Experiment &amp; Learning",
    }
    for path, label in expected.items():
        response = authenticated_client.get(path)
        assert response.status_code == 200
        assert label in response.text
        assert "Truth" in response.text
        assert "Signals" in response.text
        assert "Concepts" in response.text
        assert "Challenge" in response.text
        assert "Result" in response.text
        assert "Learning" in response.text


def test_leasedesk_truth_and_claim_warning_are_visible(authenticated_client: TestClient):
    response = authenticated_client.get("/truth")
    assert "Small-commercial-property landlords" in response.text
    assert "Record a tenant payment" in response.text
    assert "quantified time savings" in response.text
    assert "Confirmed" in response.text
    assert "Inferred" in response.text


def test_security_headers_are_present(authenticated_client: TestClient):
    response = authenticated_client.get("/truth")
    assert response.headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "unsafe-eval" not in response.headers["content-security-policy"]
