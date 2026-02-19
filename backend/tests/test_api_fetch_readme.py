def test_fetch_readme_ok(monkeypatch, client):
    from readme_to_feishu.api import routes

    def fake_fetch_readme_from_github(github_url: str, branch=None):
        return {
            "file_id": "fake-file-id",
            "preview_markdown": "# Fake\n",
            "repo_meta": {"full_name": "owner/repo"},
        }

    monkeypatch.setattr(routes, "fetch_readme_from_github", fake_fetch_readme_from_github)
    resp = client.post("/api/fetch-readme", json={"github_url": "https://github.com/owner/repo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_id"] == "fake-file-id"
    assert "preview_markdown" in data


def test_fetch_readme_bad_url(monkeypatch, client):
    # Simulate the service raising a ValueError -> 400
    from readme_to_feishu.api import routes

    def bad(_url: str, _branch=None):
        raise ValueError("Invalid GitHub URL")

    monkeypatch.setattr(routes, "fetch_readme_from_github", bad)
    resp = client.post("/api/fetch-readme", json={"github_url": "not-a-url"})
    assert resp.status_code == 400
