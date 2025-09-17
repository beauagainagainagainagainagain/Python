import json
from typing import Any

import pytest
import requests

from .github_gist import CREATE_GIST_ENDPOINT, GitHubAPIError, create_gist, get_gist


class FakeResponse:
    def __init__(self, status_code: int, data: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._data))


def test_create_gist(monkeypatch):
    expected_payload = {
        "description": "My first gist",
        "public": True,
        "files": {"file1.txt": {"content": "Aren't gists great!"}},
    }

    def mock_post(url, *, json, headers, timeout):  # noqa: A002 - required signature
        assert url == CREATE_GIST_ENDPOINT
        assert json == expected_payload
        assert headers["Accept"] == "application/vnd.github.v3+json"
        assert headers["Authorization"].startswith("token ")
        assert timeout == 10
        data = {"id": "example-id", "files": expected_payload["files"]}
        return FakeResponse(201, data)

    monkeypatch.setattr(requests, "post", mock_post)

    response = create_gist(
        description="My first gist",
        files={"file1.txt": {"content": "Aren't gists great!"}},
        auth_token="abc123",
    )
    assert response["id"] == "example-id"
    assert "file1.txt" in response["files"]


def test_get_gist(monkeypatch):
    gist_id = "example-id"
    expected = {"id": gist_id, "files": {"file1.txt": {"content": "data"}}}

    def mock_get(url, *, headers, timeout):
        assert url == f"{CREATE_GIST_ENDPOINT}/{gist_id}"
        assert headers["Accept"] == "application/vnd.github.v3+json"
        assert headers["Authorization"].startswith("token ")
        assert timeout == 10
        return FakeResponse(200, expected)

    monkeypatch.setattr(requests, "get", mock_get)

    response = get_gist(gist_id, auth_token="abc123")
    assert response == expected


def test_error_is_raised_on_failure(monkeypatch):
    def mock_post(url, *, json, headers, timeout):  # noqa: A002 - required signature
        return FakeResponse(422, text="unprocessable")

    monkeypatch.setattr(requests, "post", mock_post)

    with pytest.raises(GitHubAPIError):
        create_gist("desc", {"file.txt": {"content": "data"}}, auth_token="token")
