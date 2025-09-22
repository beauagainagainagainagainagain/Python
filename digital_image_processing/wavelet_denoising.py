"""Wavelet-based image denoising example."""

from __future__ import annotations

import math
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

try:
    import pywt  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    pywt = None  # type: ignore[assignment]

try:
    from skimage import data  # type: ignore[import-not-found]
    from skimage.metrics import peak_signal_noise_ratio  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    data = None  # type: ignore[assignment]
    peak_signal_noise_ratio = None  # type: ignore[assignment]


def im2double(image: np.ndarray) -> np.ndarray:
    """Return the image converted to ``float64`` precision.

    If the input image already contains floating point values the image is
    returned cast to ``float64`` without further scaling.  Integer images are
    scaled to the ``[0, 1]`` range, matching MATLAB's :func:`im2double`
    behaviour.
    """

    if np.issubdtype(image.dtype, np.floating):
        return image.astype(np.float64)

    info = np.iinfo(image.dtype)
    return image.astype(np.float64) / info.max


def normalize_img(image: np.ndarray) -> np.ndarray:
    """Clip image data to the ``[0, 1]`` range."""

    return np.clip(image, 0.0, 1.0)


def denoise_image_wavelet(
    original_img: np.ndarray,
    noise_level: float = 0.1,
    wavelet_name: str = "db4",
    decomposition_level: int = 3,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Denoise an image using wavelet thresholding.

    The function adds synthetic Gaussian noise to ``original_img`` and then
    performs wavelet thresholding to suppress the noise.

    Args:
        original_img: Clean input image in the ``[0, 1]`` range.
        noise_level: Standard deviation of the synthetic Gaussian noise.
        wavelet_name: Name of the wavelet family to use.
        decomposition_level: Number of wavelet decomposition levels.
        rng: Optional ``numpy`` random number generator for reproducibility.

    Returns:
        A tuple ``(noisy_img, denoised_img)`` containing the noisy and
        denoised images respectively.
    """

    if pywt is None:
        msg = "pywt is required for wavelet denoising; install PyWavelets to use this function."
        raise ModuleNotFoundError(msg)

    wavelet_module: Any = pywt

    if rng is None:
        rng = np.random.default_rng()

    original_img = im2double(original_img)

    noisy_img = original_img + noise_level * rng.standard_normal(original_img.shape)
    noisy_img = normalize_img(noisy_img)

    coeffs = wavelet_module.wavedec2(noisy_img, wavelet_name, level=decomposition_level)
    coeffs_approx = coeffs[0]
    coeffs_details = coeffs[1:]

    detail_coeffs = [
        detail_array.ravel()
        for level_details in coeffs_details
        for detail_array in level_details
    ]
    if not detail_coeffs:
        msg = "Wavelet decomposition did not produce detail coefficients."
        raise ValueError(msg)
    all_detail_coeffs = np.concatenate(detail_coeffs)

    sigma = np.median(np.abs(all_detail_coeffs)) / 0.6745
    threshold = sigma * math.sqrt(2.0 * math.log(original_img.size))

    denoised_details = [
        tuple(
            wavelet_module.threshold(detail_array, threshold, mode="soft")
            for detail_array in level_details
        )
        for level_details in coeffs_details
    ]
    coeffs_denoised = [coeffs_approx, *denoised_details]

    denoised_img = wavelet_module.waverec2(coeffs_denoised, wavelet_name)
    denoised_img = denoised_img[: original_img.shape[0], : original_img.shape[1]]
    denoised_img = normalize_img(denoised_img)

    return noisy_img, denoised_img


def main() -> None:
    """Run the wavelet denoising example and display the results."""

    if pywt is None:
        msg = "pywt is required for the wavelet denoising demo. Install PyWavelets to run it."
        raise SystemExit(msg)
    if data is None or peak_signal_noise_ratio is None:
        msg = "scikit-image is required for the wavelet denoising demo. Install scikit-image to run it."
        raise SystemExit(msg)

    original_img = im2double(data.camera())
    noisy_img, denoised_img = denoise_image_wavelet(original_img)

    psnr_noisy = peak_signal_noise_ratio(original_img, noisy_img)
    psnr_denoised = peak_signal_noise_ratio(original_img, denoised_img)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    ax = axes[0]
    ax.imshow(original_img, cmap="gray")
    ax.set_title("Original Image")
    ax.axis("off")

    ax = axes[1]
    ax.imshow(noisy_img, cmap="gray")
    ax.set_title(f"Noisy Image (PSNR: {psnr_noisy:.2f} dB)")
    ax.axis("off")

    ax = axes[2]
    ax.imshow(denoised_img, cmap="gray")
    ax.set_title(f"Denoised Image (PSNR: {psnr_denoised:.2f} dB)")
    ax.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
