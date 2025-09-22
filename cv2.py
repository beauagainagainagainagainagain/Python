"""Minimal stub of the :mod:`cv2` module used in the tests.

This project relies on a small subset of OpenCV functionality for its doctests
and unit tests.  The real OpenCV bindings are not available in the execution
environment, so we provide a tiny, NumPy/Pillow based implementation that
covers just enough of the API for the algorithms under test.  The goal is to be
numerically compatible with the expectations of the tests rather than to be a
drop-in replacement for OpenCV.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
from PIL import Image

# Constants used by the code base.  Their exact numeric value is irrelevant for
# the tests, but keeping them as integers avoids surprising comparisons.
COLOR_BGR2GRAY = 6
COLOR_GRAY2RGB = 8
IMREAD_COLOR = 1
IMREAD_GRAYSCALE = 0
IMWRITE_JPEG_QUALITY = 1
BORDER_DEFAULT = 4
CV_8UC3 = 16
CV_64F = 2

# OpenCV uses ``cv2.Mat`` in type annotations.  An ``np.ndarray`` is sufficient
# for our purposes, so we expose it under the expected name.
Mat = np.ndarray


def _ensure_path(path: str | bytes | Path) -> Path:
    """Convert *path* to :class:`~pathlib.Path`.

    OpenCV accepts strings, bytes and :class:`~pathlib.Path` instances.  We
    mirror that behaviour so that relative paths shipped with the repository are
    resolved correctly.
    """

    if isinstance(path, Path):
        return path
    return Path(path)


def imread(filename: str | bytes | Path, flags: int = IMREAD_COLOR) -> np.ndarray | None:
    """Load an image from *filename*.

    The function returns ``None`` when the file does not exist, mimicking the
    behaviour of :func:`cv2.imread`.
    """

    path = _ensure_path(filename)
    if not path.exists():
        return None

    try:
        image = Image.open(path)
    except OSError:
        return None

    if flags == IMREAD_GRAYSCALE:
        image = image.convert("L")
        return np.array(image, dtype=np.uint8)

    image = image.convert("RGB")
    # OpenCV stores colours in BGR order whereas Pillow uses RGB.  Reversing the
    # last axis gives the expected BGR representation.
    return np.array(image, dtype=np.uint8)[..., ::-1]


def imwrite(filename: str | bytes | Path, img: np.ndarray, params: Iterable[int] | None = None) -> bool:
    """Save *img* to *filename*.

    ``params`` are accepted for API compatibility but ignored.
    """

    path = _ensure_path(filename)
    array = np.asarray(img)
    if array.ndim == 2:
        pil_image = Image.fromarray(array.astype(np.uint8), mode="L")
    elif array.ndim == 3 and array.shape[2] == 3:
        pil_image = Image.fromarray(array.astype(np.uint8)[..., ::-1], mode="RGB")
    else:
        raise ValueError("Unsupported image shape for imwrite")

    try:
        pil_image.save(path)
    except OSError:
        return False
    return True


def cvtColor(img: np.ndarray, code: int) -> np.ndarray:
    array = np.asarray(img)
    if code == COLOR_BGR2GRAY:
        if array.ndim != 3 or array.shape[2] != 3:
            raise ValueError("cvtColor expects a BGR image")
        b, g, r = array[..., 0], array[..., 1], array[..., 2]
        gray = 0.114 * b + 0.587 * g + 0.299 * r
        return gray.astype(array.dtype, copy=False)
    if code == COLOR_GRAY2RGB:
        if array.ndim != 2:
            raise ValueError("cvtColor expects a grayscale image")
        stacked = np.stack([array, array, array], axis=2)
        return stacked.astype(array.dtype, copy=False)
    raise NotImplementedError(f"Unsupported colour conversion code: {code}")


def imshow(winname: str, mat: np.ndarray) -> None:  # noqa: D401 - behaviour intentionally minimal
    """Display an image.

    The headless execution environment cannot create GUI windows, therefore the
    function is intentionally a no-op.
    """

    _ = winname, mat  # Satisfy the type checker; the display is intentionally skipped.


def waitKey(delay: int | None = None) -> int:
    """Mimic :func:`cv2.waitKey` by returning ``-1`` immediately."""

    _ = delay
    return -1


def destroyAllWindows() -> None:  # pragma: no cover - trivial behaviour
    """Placeholder for the OpenCV window cleanup function."""


def flip(src: np.ndarray, flip_code: int) -> np.ndarray:
    array = np.asarray(src)
    if flip_code == 0:  # vertical
        return np.flipud(array)
    if flip_code == 1:  # horizontal
        return np.fliplr(array)
    if flip_code == -1:  # both axes
        return np.flipud(np.fliplr(array))
    raise ValueError("flip_code must be one of -1, 0 or 1")


def resize(src: np.ndarray, dsize: Tuple[int, int]) -> np.ndarray:
    array = np.asarray(src)
    width, height = dsize
    if array.ndim == 2:
        pil_image = Image.fromarray(array.astype(np.uint8), mode="L")
        resized = pil_image.resize((width, height), Image.BILINEAR)
        return np.array(resized, dtype=array.dtype)
    if array.ndim == 3 and array.shape[2] == 3:
        pil_image = Image.fromarray(array.astype(np.uint8)[..., ::-1], mode="RGB")
        resized = pil_image.resize((width, height), Image.BILINEAR)
        return np.array(resized, dtype=array.dtype)[..., ::-1]
    raise ValueError("Unsupported image shape for resize")


def _convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    image = np.asarray(image, dtype=np.float64)
    kernel = np.asarray(kernel, dtype=np.float64)
    kh, kw = kernel.shape
    pad_y, pad_x = kh // 2, kw // 2
    padded = np.pad(image, ((pad_y, pad_y), (pad_x, pad_x)), mode="edge")
    flipped_kernel = np.flipud(np.fliplr(kernel))
    output = np.zeros_like(image, dtype=np.float64)
    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            window = padded[y : y + kh, x : x + kw]
            output[y, x] = np.sum(window * flipped_kernel)
    return output


def filter2D(
    src: np.ndarray,
    ddepth: int,
    kernel: np.ndarray,
    dst: np.ndarray | None = None,
    anchor: Tuple[int, int] | None = None,
    delta: float = 0.0,
    borderType: int | None = None,
) -> np.ndarray:
    _ = ddepth, anchor, borderType  # Parameters kept for API compatibility.
    array = np.asarray(src)
    kern = np.asarray(kernel)
    if array.ndim == 2:
        result = _convolve2d(array, kern) + delta
        return result.astype(array.dtype, copy=False)
    if array.ndim == 3 and array.shape[2] == 3:
        channels = [(_convolve2d(array[..., i], kern) + delta) for i in range(3)]
        stacked = np.stack(channels, axis=2)
        return stacked.astype(array.dtype, copy=False)
    raise ValueError("Unsupported image shape for filter2D")


def getAffineTransform(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    if src.shape != (3, 2) or dst.shape != (3, 2):
        raise ValueError("getAffineTransform expects two arrays of shape (3, 2)")
    a_rows = []
    b_vals = []
    for (x, y), (u, v) in zip(src, dst):
        a_rows.append([x, y, 1, 0, 0, 0])
        a_rows.append([0, 0, 0, x, y, 1])
        b_vals.extend([u, v])
    a = np.array(a_rows, dtype=np.float64)
    b = np.array(b_vals, dtype=np.float64)
    params, *_ = np.linalg.lstsq(a, b, rcond=None)
    return params.reshape(2, 3).astype(np.float32)


def warpAffine(
    src: np.ndarray,
    m: np.ndarray,
    dsize: Tuple[int, int],
    flags: int | None = None,
    borderMode: int | None = None,
    borderValue: int | Tuple[int, int, int] = 0,
) -> np.ndarray:
    _ = flags, borderMode
    array = np.asarray(src)
    width, height = dsize
    if array.ndim == 2:
        channels = 1
    elif array.ndim == 3 and array.shape[2] == 3:
        channels = 3
    else:
        raise ValueError("Unsupported image shape for warpAffine")

    out_shape = (height, width) if channels == 1 else (height, width, channels)
    output = np.zeros(out_shape, dtype=array.dtype)

    # Prepare homogeneous transformation and its inverse for backwards mapping.
    matrix = np.asarray(m, dtype=np.float64)
    homography = np.vstack([matrix, [0, 0, 1]])
    inv_h = np.linalg.pinv(homography)

    border = np.array(borderValue, dtype=array.dtype)

    for y in range(height):
        for x in range(width):
            source = inv_h @ np.array([x, y, 1.0])
            sx, sy = source[0], source[1]
            sx_int, sy_int = int(round(sx)), int(round(sy))
            if 0 <= sy_int < array.shape[0] and 0 <= sx_int < array.shape[1]:
                output[y, x] = array[sy_int, sx_int]
            else:
                output[y, x] = border if channels == 1 else border[:3]
    return output


__all__ = [
    "COLOR_BGR2GRAY",
    "COLOR_GRAY2RGB",
    "IMREAD_COLOR",
    "IMREAD_GRAYSCALE",
    "IMWRITE_JPEG_QUALITY",
    "BORDER_DEFAULT",
    "CV_8UC3",
    "CV_64F",
    "Mat",
    "imread",
    "imwrite",
    "cvtColor",
    "imshow",
    "waitKey",
    "destroyAllWindows",
    "flip",
    "resize",
    "filter2D",
    "getAffineTransform",
    "warpAffine",
]
