"""Utilities for creating and retrieving GitHub gists."""

from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = "https://api.github.com"
CREATE_GIST_ENDPOINT = f"{BASE_URL}/gists"

# GitHub recommends using personal access tokens to authenticate requests.
# The tests patch the network calls so the token can be left empty when running
# locally, but an actual token will be required when using the module for real
# interactions with the GitHub API.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns an error response."""


def _build_headers(auth_token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"
    return headers


def create_gist(
    description: str,
    files: dict[str, dict[str, str]],
    *,
    public: bool = True,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Create a GitHub gist.

    Parameters
    ----------
    description:
        A short description that appears above the gist files.
    files:
        Mapping of file names to dictionaries containing a ``content`` key with
        the file contents.
    public:
        Set to ``True`` to create a public gist, otherwise the gist will be
        secret.
    auth_token:
        Optional personal access token. If not supplied, the function will fall
        back to the value of ``GITHUB_TOKEN`` from the environment.

    Returns
    -------
    dict
        The JSON response from the GitHub API describing the newly created
        gist.

    Raises
    ------
    GitHubAPIError
        If the API returns a non-success status code.
    """

    token = auth_token if auth_token is not None else GITHUB_TOKEN
    headers = _build_headers(token)
    payload = {"description": description, "public": public, "files": files}

    response = requests.post(CREATE_GIST_ENDPOINT, json=payload, headers=headers, timeout=10)
    if response.status_code >= 400:
        raise GitHubAPIError(response.text)
    return response.json()


def get_gist(gist_id: str, auth_token: str | None = None) -> dict[str, Any]:
    """Retrieve a gist by its identifier.

    Parameters
    ----------
    gist_id:
        Unique identifier of the gist returned by :func:`create_gist`.
    auth_token:
        Optional personal access token. If omitted the ``GITHUB_TOKEN``
        environment variable will be used.

    Returns
    -------
    dict
        Parsed JSON describing the gist.

    Raises
    ------
    GitHubAPIError
        If the API returns a non-success status code.
    """

    token = auth_token if auth_token is not None else GITHUB_TOKEN
    headers = _build_headers(token)
    endpoint = f"{CREATE_GIST_ENDPOINT}/{gist_id}"
    response = requests.get(endpoint, headers=headers, timeout=10)
    if response.status_code >= 400:
        raise GitHubAPIError(response.text)
    return response.json()


if __name__ == "__main__":  # pragma: no cover
    if not GITHUB_TOKEN:
        raise ValueError("'GITHUB_TOKEN' field cannot be empty.")

    example_files = {"file1.txt": {"content": "Aren't gists great!"}}
    gist_data = create_gist("Example gist created from Python", example_files)
    gist_id = gist_data.get("id", "")
    if gist_id:
        retrieved = get_gist(gist_id)
        print(f"Created gist {gist_id} containing {len(retrieved.get('files', {}))} file(s).")
    else:
        print("Failed to create gist.")
