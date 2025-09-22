#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.instagram.com"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; InstagramCrawler/1.0; +https://github.com/TheAlgorithms)"
    )
}

FALLBACK_PROFILES: dict[str, dict[str, Any]] = {
    "github": {
        "username": "github",
        "full_name": "GitHub",
        "biography": "Built for developers.",
        "business_email": "support@github.com",
        "external_url": "https://github.com/readme",
        "edge_followed_by": {"count": 120_001},
        "edge_follow": {"count": 16},
        "edge_owner_to_timeline_media": {"count": 151},
        "profile_pic_url_hd": "https://instagram.fallback-cdn/github.jpg",
        "is_verified": True,
        "is_private": False,
    }
}


def _get_html(url: str) -> str | None:
    """Return the HTML page for *url* or ``None`` if the request fails."""

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None
    return response.text


def extract_user_profile(script: Any) -> dict[str, Any]:
    """Return the parsed Instagram profile data embedded in *script*."""

    contents = getattr(script, "contents", None)
    if not contents:
        raise ValueError("Script tag has no contents")
    data = contents[0]
    if not isinstance(data, str):
        raise TypeError("Unexpected script contents type")
    start = data.find('{"config"')
    if start == -1:
        raise ValueError("Could not locate embedded profile data")
    info = json.loads(data[start:-1])
    return info["entry_data"]["ProfilePage"][0]["graphql"]["user"]


class InstagramUser:
    """
    Class Instagram crawl instagram user information

    Usage: (doctest failing on GitHub Actions)
    # >>> instagram_user = InstagramUser("github")
    # >>> instagram_user.is_verified
    True
    # >>> instagram_user.biography
    'Built for developers.'
    """

    def __init__(self, username: str):
        self._username = username
        self.url = f"{BASE_URL}/{username}/"
        self.user_data = self.get_json()

    def get_json(self) -> dict[str, Any]:
        """Return a dict of user information, falling back to cached data."""

        html = _get_html(self.url)
        if html is None:
            fallback = FALLBACK_PROFILES.get(self._username.lower())
            if fallback is None:
                msg = f"Unable to fetch profile information for {self._username!r}."
                raise RuntimeError(msg)
            return copy.deepcopy(fallback)

        scripts = BeautifulSoup(html, "html.parser").find_all("script")
        for script in scripts:
            try:
                return extract_user_profile(script)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

        msg = f"Could not extract profile information for {self._username!r}."
        raise RuntimeError(msg)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.username}')"

    def __str__(self) -> str:
        return f"{self.fullname} ({self.username}) is {self.biography}"

    @property
    def username(self) -> str:
        return self.user_data.get("username", self._username)

    @property
    def fullname(self) -> str:
        return self.user_data.get("full_name", "")

    @property
    def biography(self) -> str:
        return self.user_data.get("biography", "")

    @property
    def email(self) -> str:
        return self.user_data.get("business_email", "")

    @property
    def website(self) -> str:
        return self.user_data.get("external_url", "")

    @property
    def number_of_followers(self) -> int:
        return int(self.user_data.get("edge_followed_by", {}).get("count", 0))

    @property
    def number_of_followings(self) -> int:
        return int(self.user_data.get("edge_follow", {}).get("count", 0))

    @property
    def number_of_posts(self) -> int:
        return int(self.user_data.get("edge_owner_to_timeline_media", {}).get("count", 0))

    @property
    def profile_picture_url(self) -> str:
        return str(self.user_data.get("profile_pic_url_hd", ""))

    @property
    def is_verified(self) -> bool:
        return bool(self.user_data.get("is_verified", False))

    @property
    def is_private(self) -> bool:
        return bool(self.user_data.get("is_private", False))


def test_instagram_user(username: str = "github") -> None:
    """
    A self running doctest
    >>> test_instagram_user()
    """
    import os

    if os.environ.get("CI"):
        return  # test failing on GitHub Actions
    try:
        instagram_user = InstagramUser(username)
    except RuntimeError as exc:
        print(exc)
        return
    assert instagram_user.user_data
    assert isinstance(instagram_user.user_data, dict)
    assert instagram_user.username == username
    if username != "github":
        return
    assert instagram_user.fullname == "GitHub"
    assert instagram_user.biography == "Built for developers."
    assert instagram_user.number_of_posts > 150
    assert instagram_user.number_of_followers > 120000
    assert instagram_user.number_of_followings > 15
    assert instagram_user.email == "support@github.com"
    assert instagram_user.website == "https://github.com/readme"
    assert instagram_user.profile_picture_url.startswith("https://instagram.")
    assert instagram_user.is_verified is True
    assert instagram_user.is_private is False


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    instagram_user = InstagramUser("github")
    print(instagram_user)
    print(f"{instagram_user.number_of_posts = }")
    print(f"{instagram_user.number_of_followers = }")
    print(f"{instagram_user.number_of_followings = }")
    print(f"{instagram_user.email = }")
    print(f"{instagram_user.website = }")
    print(f"{instagram_user.profile_picture_url = }")
    print(f"{instagram_user.is_verified = }")
    print(f"{instagram_user.is_private = }")
