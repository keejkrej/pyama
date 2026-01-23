"""
Tests for kinetic model fitting.
"""

import numpy as np
import pytest

from pyama_core.analysis.fitting import fit_model
from pyama_core.analysis.models import get_model
from pyama_core.types.analysis import FitParam, FitParams, FixedParam, FixedParams


class TestMaturationModel:
    """Tests for maturation kinetic model."""

    def setup_method(self):
        """Set up test fixtures."""
        self.model = get_model("maturation")
        self.default_fixed = self.model.DEFAULT_FIXED
        self.default_fit = self.model.DEFAULT_FIT

    def test_model_eval_basic(self):
        """Test basic evaluation of maturation model."""
        t = np.array([0, 1, 2, 3, 4, 5], dtype=np.float64)

        result = self.model.eval(t, self.default_fixed, self.default_fit)

        assert isinstance(result, np.ndarray)
        assert len(result) == len(t)
        # Result should be positive (baseline offset might shift this)
        assert np.all(np.isfinite(result))

    def test_model_eval_at_t0(self):
        """Test that model evaluates to zero before t0."""
        t0 = self.default_fit["t0"].value
        t_before = np.array([t0 - 2, t0 - 1], dtype=np.float64)

        result = self.model.eval(t_before, self.default_fixed, self.default_fit)

        # Before t0, should be only the offset
        expected = self.default_fit["offset"].value
        # Allow small numerical error
        assert np.allclose(result, expected, atol=1e-6)

    def test_model_eval_after_t0(self):
        """Test that model grows after t0."""
        t0 = self.default_fit["t0"].value
        t = np.array([t0, t0 + 1, t0 + 5, t0 + 10], dtype=np.float64)

        result = self.model.eval(t, self.default_fixed, self.default_fit)

        # Should increase with time after t0
        assert result[-1] > result[0]
        # All should be finite
        assert np.all(np.isfinite(result))

    def test_fit_model_synthetic_data(self):
        """Test fitting model to synthetic data generated from model."""
        np.random.seed(42)

        # Generate synthetic data from model
        t_true = np.linspace(0, 20, 100)
        y_true = self.model.eval(t_true, self.default_fixed, self.default_fit)
        # Add noise
        noise = np.random.normal(0, 0.1 * np.max(y_true), size=len(y_true))
        y_data = y_true + noise

        # Fit model
        result = fit_model(
            self.model,
            t_true,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        assert result.success is True
        assert result.r_squared > 0.9  # Good fit should have high R²
        assert result.fitted_params is not None
        # Fitted t0 should be close to true t0
        fitted_t0 = result.fitted_params["t0"].value
        assert abs(fitted_t0 - self.default_fit["t0"].value) < 1.0

    def test_fit_model_insufficient_data(self):
        """Test fitting with insufficient data points."""
        t_data = np.array([0, 1, 2], dtype=np.float64)
        y_data = np.array([100, 200, 300], dtype=np.float64)

        # More fit parameters than data points
        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        assert result.success is False
        assert result.r_squared == 0.0

    def test_fit_model_with_nan(self):
        """Test fitting with NaN values in data."""
        t_data = np.array([0, 1, 2, np.nan, 4, 5], dtype=np.float64)
        y_data = np.array([100, 150, 200, 250, np.nan, 350], dtype=np.float64)

        # Should clean data and still fit
        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        # Should work with cleaned data
        assert result.fitted_params is not None

    def test_fit_model_parameter_bounds(self):
        """Test that fitted parameters respect bounds."""
        t_data = np.linspace(0, 20, 100)
        y_data = self.model.eval(t_data, self.default_fixed, self.default_fit)

        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        # All fitted parameters should be within bounds
        for param_name, param in result.fitted_params.items():
            assert param.lb <= param.value <= param.ub

    def test_fit_model_r_squared_computation(self):
        """Test that R² is computed correctly."""
        t_data = np.linspace(0, 20, 100)
        y_data = self.model.eval(t_data, self.default_fixed, self.default_fit)

        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        # Perfect fit should have R² close to 1
        assert 0.95 < result.r_squared <= 1.0

    def test_fit_model_poor_data(self):
        """Test fitting on random noise (should have low R²)."""
        np.random.seed(42)
        t_data = np.linspace(0, 20, 100)
        y_data = np.random.normal(150, 50, size=len(t_data))

        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        # Poor fit should have low R²
        assert result.r_squared < 0.5

    def test_default_parameters_exist(self):
        """Test that model has required default parameters."""
        assert hasattr(self.model, "DEFAULT_FIXED")
        assert hasattr(self.model, "DEFAULT_FIT")

        assert isinstance(self.model.DEFAULT_FIXED, dict)
        assert isinstance(self.model.DEFAULT_FIT, dict)

        # Check required fixed parameters
        assert "km" in self.model.DEFAULT_FIXED
        assert "beta" in self.model.DEFAULT_FIXED
        assert "scale" in self.model.DEFAULT_FIXED

        # Check required fit parameters
        assert "t0" in self.model.DEFAULT_FIT
        assert "ktl" in self.model.DEFAULT_FIT
        assert "delta" in self.model.DEFAULT_FIT
        assert "offset" in self.model.DEFAULT_FIT

    def test_fixed_param_structure(self):
        """Test that fixed parameters have correct structure."""
        for param_name, param in self.model.DEFAULT_FIXED.items():
            assert isinstance(param, FixedParam)
            assert hasattr(param, "name")
            assert hasattr(param, "value")
            assert isinstance(param.value, (int, float))

    def test_fit_param_structure(self):
        """Test that fit parameters have correct structure."""
        for param_name, param in self.model.DEFAULT_FIT.items():
            assert isinstance(param, FitParam)
            assert hasattr(param, "name")
            assert hasattr(param, "value")
            assert hasattr(param, "lb")
            assert hasattr(param, "ub")
            assert isinstance(param.value, (int, float))
            assert isinstance(param.lb, (int, float))
            assert isinstance(param.ub, (int, float))
            assert param.lb <= param.value <= param.ub

    def test_fit_result_structure(self):
        """Test that fit result has expected structure."""
        t_data = np.linspace(0, 20, 50)
        y_data = self.model.eval(t_data, self.default_fixed, self.default_fit)

        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=self.default_fit,
        )

        # Check result attributes
        assert hasattr(result, "fixed_params")
        assert hasattr(result, "fitted_params")
        assert hasattr(result, "success")
        assert hasattr(result, "r_squared")

        assert isinstance(result.success, bool)
        assert isinstance(result.r_squared, float)
        assert 0.0 <= result.r_squared <= 1.0

    def test_custom_fixed_parameters(self):
        """Test fitting with custom fixed parameters."""
        custom_fixed: FixedParams = {
            "km": FixedParam(name="Maturation Rate", value=2.0),
            "beta": FixedParam(name="Degradation Rate", value=0.011),  # avoid beta==delta
            "scale": FixedParam(name="Scale Factor", value=1.0),
        }

        t_data = np.linspace(0, 20, 100)
        y_data = self.model.eval(t_data, custom_fixed, self.default_fit)

        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=custom_fixed,
            fit_params=self.default_fit,
        )

        assert result.success is True
        # Result should use the custom fixed parameters
        assert result.fixed_params == custom_fixed

    def test_custom_fit_parameters(self):
        """Test fitting with custom fit parameter bounds."""
        custom_fit: FitParams = {
            "t0": FitParam(name="Time Zero", value=5, lb=0, ub=10),
            "ktl": FitParam(name="Translation Rate", value=1e3, lb=1, ub=1e6),
            "delta": FitParam(name="Decay Rate", value=0.05, lb=0.01, ub=1),
            "offset": FitParam(name="Baseline Offset", value=0, lb=-100, ub=100),
        }

        t_data = np.linspace(0, 20, 100)
        y_true = self.model.eval(t_data, self.default_fixed, custom_fit)
        np.random.seed(42)
        y_data = y_true + np.random.normal(0, 0.01 * np.max(y_true), len(y_true))

        result = fit_model(
            self.model,
            t_data,
            y_data,
            fixed_params=self.default_fixed,
            fit_params=custom_fit,
        )

        # All fitted values should be within custom bounds
        for param_name, param in result.fitted_params.items():
            assert param.lb <= param.value <= param.ub


class TestModelRegistry:
    """Tests for model registration and access."""

    def test_get_maturation_model(self):
        """Test that maturation model can be retrieved."""
        model = get_model("maturation")
        assert model is not None
        assert hasattr(model, "eval")
        assert callable(model.eval)

    def test_get_unknown_model_raises(self):
        """Test that unknown model raises error."""
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("unknown_model_xyz")

    def test_model_case_insensitive(self):
        """Test that model names are case-insensitive."""
        model_lower = get_model("maturation")
        model_upper = get_model("MATURATION")
        model_mixed = get_model("Maturation")

        # All should return the same model
        assert model_lower is model_upper
        assert model_lower is model_mixed
