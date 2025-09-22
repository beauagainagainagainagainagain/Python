from __future__ import annotations

import builtins
import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@contextmanager
def reload_module(module_name: str, blocked: tuple[str, ...] = ()):
    """Reload *module_name* while temporarily blocking imports listed in *blocked*."""

    for key in list(sys.modules):
        if key == module_name or key.startswith(f"{module_name}."):
            del sys.modules[key]

    if blocked:
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if any(name == target or name.startswith(f"{target}.") for target in blocked):
                raise ImportError(f"No module named {name}")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", new=fake_import):
            module = importlib.import_module(module_name)
            try:
                yield module
            finally:
                sys.modules.pop(module_name, None)
    else:
        module = importlib.import_module(module_name)
        try:
            yield module
        finally:
            sys.modules.pop(module_name, None)


def test_cnn_classification_import_without_tensorflow():
    with reload_module(
        "computer_vision.cnn_classification", blocked=("tensorflow", "keras")
    ) as module:
        assert module.tf is None
        assert module.layers is None
        assert module.models is None


def test_k_means_tensorflow_requires_tensorflow():
    with reload_module(
        "dynamic_programming.k_means_clustering_tensorflow", blocked=("tensorflow",)
    ) as module:
        assert module.tf is None
        data = np.array([[0.0, 0.0], [1.0, 1.0]])
        with pytest.raises(ImportError, match="TensorFlow is required"):
            module.tf_k_means_cluster(data, 1)


def test_lstm_prediction_import_without_optional_dependencies():
    with reload_module(
        "machine_learning.lstm.lstm_prediction", blocked=("keras", "sklearn")
    ) as module:
        assert module.LSTM is None
        assert module.Dense is None
        assert module.Sequential is None
        assert module.MinMaxScaler is None


def test_input_data_fallback_dataset(tmp_path, monkeypatch):
    with reload_module("neural_network.input_data", blocked=("tensorflow",)) as module:
        assert module.dtypes.float32 == module.dtypes.as_dtype(np.float32)
        assert module.dtypes.uint8 == module.dtypes.as_dtype(np.uint8)

        images = np.arange(16, dtype=np.uint8).reshape(4, 2, 2, 1)
        labels = np.arange(4, dtype=np.uint8)
        dataset = module._DataSet(
            images, labels, dtype=module.dtypes.float32, reshape=True, seed=123
        )
        batch_images, batch_labels = dataset.next_batch(3, shuffle=False)
        assert batch_images.shape == (3, 4)
        assert batch_labels.shape == (3,)
        assert batch_images.dtype == np.float32
        assert np.all((0.0 <= batch_images) & (batch_images <= 1.0))

        seed1, seed2 = module.random_seed.get_seed(None)
        assert isinstance(seed1, int) and isinstance(seed2, int)

        filename = "sample.bin"

        def fake_urlretrieve(url, filename):  # noqa: ARG001 - signature matches stdlib
            Path(filename).write_bytes(b"data")
            return filename, None

        module.urllib.request = types.SimpleNamespace(urlretrieve=fake_urlretrieve)
        path = module._maybe_download(filename, tmp_path, "http://example.com/sample.bin")
        assert Path(path).read_bytes() == b"data"


def test_wavelet_denoising_requires_pywt():
    with reload_module(
        "digital_image_processing.wavelet_denoising", blocked=("pywt",)
    ) as module:
        assert module.pywt is None
        image = np.zeros((4, 4), dtype=float)
        with pytest.raises(ModuleNotFoundError, match="pywt is required"):
            module.denoise_image_wavelet(image)


def test_ctrl_dashboard_requires_jinja2(tmp_path):
    with reload_module(
        "sustainability.ctrl_compliance_dashboard", blocked=("jinja2",)
    ) as module:
        assert module.Environment is None
        html_path = tmp_path / "report.html"
        meta = module.Metadata("Site", "Client", "Inspector", "2024-01-01")
        with pytest.raises(ModuleNotFoundError, match="jinja2 is required"):
            module.render_report(object(), meta, "logo.png", str(html_path), None)


def test_fetch_anime_and_play_handles_network_errors(monkeypatch):
    from web_programming import fetch_anime_and_play as module

    def fake_get(*args, **kwargs):  # noqa: ARG001 - signature compatibility
        raise requests.RequestException("offline")

    monkeypatch.setattr(module.requests, "get", fake_get)

    assert module.search_scraper("demon_slayer") == []
    assert module.search_anime_episode_list("/anime/kimetsu-no-yaiba") == []
    assert module.get_anime_episode("/watch/kimetsu-no-yaiba/1") == []


def test_instagram_user_falls_back_to_cached_profile(monkeypatch):
    from web_programming import instagram_crawler as module

    def fake_get(*args, **kwargs):  # noqa: ARG001 - signature compatibility
        raise requests.RequestException("offline")

    monkeypatch.setattr(module.requests, "get", fake_get)

    original_followers = module.FALLBACK_PROFILES["github"]["edge_followed_by"]["count"]
    user = module.InstagramUser("github")

    assert user.username == "github"
    assert user.fullname == "GitHub"
    assert user.biography == "Built for developers."
    assert user.number_of_posts >= 151
    assert user.number_of_followers == original_followers
    assert module.FALLBACK_PROFILES["github"]["edge_followed_by"]["count"] == original_followers
    assert user.profile_picture_url.startswith("https://instagram.")
