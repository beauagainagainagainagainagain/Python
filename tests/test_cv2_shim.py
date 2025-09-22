from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cv2", ROOT / "cv2.py")
cv2 = importlib.util.module_from_spec(spec)
sys.modules["cv2"] = cv2
spec.loader.exec_module(cv2)


def test_imwrite_and_imread_color_roundtrip(tmp_path):
    image = np.array(
        [
            [[10, 20, 30], [40, 50, 60]],
            [[70, 80, 90], [100, 110, 120]],
        ],
        dtype=np.uint8,
    )
    path = tmp_path / "color.png"
    assert cv2.imwrite(path, image)
    loaded = cv2.imread(path)
    assert loaded is not None
    np.testing.assert_array_equal(loaded, image)


def test_imwrite_and_imread_grayscale(tmp_path):
    image = np.array([[0, 64], [128, 255]], dtype=np.uint8)
    path = tmp_path / "gray.png"
    assert cv2.imwrite(path, image)
    loaded = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    assert loaded is not None
    np.testing.assert_array_equal(loaded, image)


def test_cvtcolor_bgr2gray_and_gray2rgb():
    bgr = np.array([[[10, 20, 30], [200, 150, 100]]], dtype=np.uint8)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    expected_gray = np.array(
        [[0.114 * 10 + 0.587 * 20 + 0.299 * 30, 0.114 * 200 + 0.587 * 150 + 0.299 * 100]],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(gray, expected_gray)

    recovered = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    np.testing.assert_array_equal(
        recovered,
        np.stack([gray, gray, gray], axis=2),
    )


def test_flip_and_resize():
    image = np.arange(9, dtype=np.uint8).reshape(3, 3)
    assert np.array_equal(cv2.flip(image, 0), np.array([[6, 7, 8], [3, 4, 5], [0, 1, 2]]))
    assert np.array_equal(cv2.flip(image, 1), np.array([[2, 1, 0], [5, 4, 3], [8, 7, 6]]))
    assert np.array_equal(cv2.flip(image, -1), np.array([[8, 7, 6], [5, 4, 3], [2, 1, 0]]))

    color = np.array([[[10, 20, 30]]], dtype=np.uint8)
    resized = cv2.resize(color, (2, 2))
    assert resized.shape == (2, 2, 3)
    assert np.all(resized == color[0, 0])


def test_filter2d_identity_kernel():
    image = np.arange(9, dtype=np.float64).reshape(3, 3)
    kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=float)
    filtered = cv2.filter2D(image, cv2.CV_64F, kernel)
    np.testing.assert_allclose(filtered, image)


def test_filter2d_blur_kernel():
    image = np.arange(9, dtype=np.float64).reshape(3, 3)
    kernel = np.ones((3, 3), dtype=float) / 9
    filtered = cv2.filter2D(image, cv2.CV_64F, kernel)
    assert pytest.approx(filtered[1, 1]) == np.mean(image)
    assert np.all(filtered >= 0)


def test_affine_transform_and_warp_affine():
    src_pts = np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32)
    dst_pts = np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32)
    matrix = cv2.getAffineTransform(src_pts, dst_pts)
    image = np.arange(9, dtype=np.uint8).reshape(3, 3)
    warped = cv2.warpAffine(image, matrix, (3, 3))
    np.testing.assert_array_equal(warped, image)

    translated_dst = np.array([[1, 0], [2, 0], [1, 1]], dtype=np.float32)
    translation = cv2.getAffineTransform(src_pts, translated_dst)
    padded = cv2.warpAffine(image, translation, (4, 3), borderValue=255)
    assert padded.shape == (3, 4)
    np.testing.assert_array_equal(padded[:, 1:], image)
