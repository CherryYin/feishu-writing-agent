"""Feishu API client - Architecture 3.4: create doc, get root block, append blocks in batches."""

from __future__ import annotations

from typing import Any

import httpx

# Feishu Open Platform base
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

def _raise_http_error(resp: httpx.Response, *, hint: str = "") -> None:
    body = ""
    try:
        body = resp.text
    except Exception:
        body = "<unreadable body>"
    msg = f"HTTP {resp.status_code} for {resp.request.method} {resp.request.url}\nResponse body: {body}"
    if hint:
        msg = hint + "\n" + msg
    raise RuntimeError(msg)


def _post_json(url: str, *, token: str | None, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            _raise_http_error(resp)
        data = resp.json()
        # Feishu OpenAPI returns {code:0,msg:"ok",data:{...}}
        if isinstance(data, dict) and data.get("code") not in (0, None):
            code = data.get("code")
            msg = data.get("msg")
            if code == 99991672:
                # Permission/scopes missing
                raise RuntimeError(
                    "Feishu permission denied (code=99991672). "
                    "Your app is missing required tenant scopes for this API. "
                    "Required scopes (one of): docx:document, docx:document:create. "
                    "Open Feishu developer console → your app → Permissions (应用身份权限) → "
                    "apply/enable these scopes, then re-authorize/install the app in the tenant. "
                    f"Original msg: {msg}"
                )
            raise RuntimeError(
                f"Feishu API error for {url}: {msg} (code={code}) data={data.get('data')}"
            )
        return data.get("data", data)


def _get_json(url: str, *, token: str, params: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code >= 400:
            _raise_http_error(resp)
        data = resp.json()
        if isinstance(data, dict) and data.get("code") not in (0, None):
            raise RuntimeError(f"Feishu API error for {url}: {data.get('msg')} (code={data.get('code')}) data={data.get('data')}")
        return data.get("data", data)


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """POST /open-apis/auth/v3/tenant_access_token/internal."""
    url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    data = _post_json(url, token=None, payload={"app_id": app_id, "app_secret": app_secret}, timeout=10.0)
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"Failed to get tenant_access_token: {data}")
    return token


def create_document(token: str, folder_token: str | None = None, title: str = "Untitled") -> dict[str, Any]:
    """POST /open-apis/docx/v1/documents - create empty doc. Returns document_id."""
    url = f"{FEISHU_API_BASE}/docx/v1/documents"
    payload: dict[str, Any] = {"title": title}
    if folder_token:
        payload["folder_token"] = folder_token
    try:
        return _post_json(url, token=token, payload=payload, timeout=15.0)
    except RuntimeError as e:
        # Common cause of HTTP 400: invalid folder_token. Retry without it to isolate.
        if folder_token:
            try:
                return _post_json(url, token=token, payload={"title": title}, timeout=15.0)
            except Exception:
                pass
        raise RuntimeError(f"Create document failed. Payload={payload}\n{e}") from e


def get_document(token: str, document_id: str) -> dict[str, Any]:
    """GET /open-apis/docx/v1/documents/{document_id} - fetch document metadata (often includes a usable URL)."""
    url = f"{FEISHU_API_BASE}/docx/v1/documents/{document_id}"
    return _get_json(url, token=token, params=None, timeout=10.0)


def get_document_block_children(token: str, document_id: str, block_id: str, page_size: int = 50) -> dict[str, Any]:
    """GET /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children."""
    url = f"{FEISHU_API_BASE}/docx/v1/documents/{document_id}/blocks/{block_id}/children"
    return _get_json(
        url,
        token=token,
        params={"document_revision_id": -1, "page_size": page_size},
        timeout=10.0,
    )


def append_document_blocks(
    token: str,
    document_id: str,
    block_id: str,
    children: list[dict[str, Any]],
    index: int | None = None,
) -> dict[str, Any]:
    """POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children (batch, ~50 per call)."""
    url = f"{FEISHU_API_BASE}/docx/v1/documents/{document_id}/blocks/{block_id}/children"
    payload: dict[str, Any] = {"children": children}
    # If index is omitted, Feishu appends to the end; negative index is invalid.
    if index is not None:
        payload["index"] = index
    try:
        return _post_json(url, token=token, payload=payload, timeout=15.0)
    except RuntimeError as e:
        sample = ""
        try:
            import json

            sample = json.dumps(children[0], ensure_ascii=False)[:1000] if children else ""
        except Exception:
            sample = "<failed to serialize sample block>"
        raise RuntimeError(
            f"Append blocks failed. count={len(children)} first_block_sample={sample}\n{e}"
        ) from e


def get_root_block_id(token: str, document_id: str) -> str:
    """Create doc returns document_id; root block is the document's root. Use block_id = document_id for root."""
    # Feishu docx: the document's root block id is typically the document_id itself or we get first child
    data = get_document_block_children(token, document_id, document_id, page_size=1)
    # Actually in Feishu Docx API, the root block might be document_id; children are appended under it
    return document_id
