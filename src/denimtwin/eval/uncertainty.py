"""Uncertainty / calibration metrics (plan §6.4)."""
import numpy as np

def interval_coverage(lo, hi, real):
    """Fraction of real values inside [lo, hi]. For an 80% interval, target ≈ 0.80."""
    lo, hi, real = map(lambda x: np.asarray(x, float), (lo, hi, real))
    return float(((real >= lo) & (real <= hi)).mean())

def calibration_error(lo, hi, real, nominal):
    return abs(interval_coverage(lo, hi, real) - nominal)

def gaussian_nll(mu, sigma, real):
    mu, s, r = map(lambda x: np.asarray(x, float), (mu, sigma, real))
    return float(np.mean(0.5 * np.log(2 * np.pi * s**2) + (r - mu)**2 / (2 * s**2)))

def confidence_error_correlation(confidence, abs_error):
    """Spearman correlation between stated confidence and actual error. Should be negative."""
    from scipy.stats import spearmanr
    return float(spearmanr(confidence, abs_error).correlation)
