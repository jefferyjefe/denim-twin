"""Fray metrics (plan §6.3). Inputs are per-position measurements along the hem."""
import numpy as np

def fray_depth_stats(depths_mm):
    d = np.asarray(depths_mm, float)
    return dict(mean=float(d.mean()), max=float(d.max()), std=float(d.std()),
                p10=float(np.percentile(d, 10)), p90=float(np.percentile(d, 90)))

def fray_depth_profile_error(pred_depths_mm, real_depths_mm):
    """Mean abs error between predicted and real depth at matched hem positions."""
    p, r = np.asarray(pred_depths_mm, float), np.asarray(real_depths_mm, float)
    assert p.shape == r.shape, "profiles must be sampled at the same hem positions"
    return float(np.abs(p - r).mean())

def thread_length_distribution_distance(pred_lengths_mm, real_lengths_mm):
    """1-D Wasserstein distance between thread-length samples."""
    from scipy.stats import wasserstein_distance
    return float(wasserstein_distance(pred_lengths_mm, real_lengths_mm))

def visible_fray_fraction(depths_mm, min_visible_mm=1.0):
    d = np.asarray(depths_mm, float)
    return float((d >= min_visible_mm).mean())

def edge_curl_error(pred_curl_mm, real_curl_mm):
    return float(np.abs(np.asarray(pred_curl_mm, float) - np.asarray(real_curl_mm, float)).mean())
