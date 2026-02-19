def test_upload_ok(client):
    resp = client.post(
        "/api/upload",
        files={"file": ("README.md", b"# Title\n\nHello", "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data and data["file_id"]
    assert "preview_markdown" in data
    assert "Title" in data["preview_markdown"]


def test_upload_rejects_non_md_txt(client):
    resp = client.post(
        "/api/upload",
        files={"file": ("README.pdf", b"%PDF", "application/pdf")},
    )
    assert resp.status_code == 400
