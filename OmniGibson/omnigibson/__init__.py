import builtins
import logging
import os
import shutil
import signal
import tempfile

# ---------------------------------------------------------------------------
# Monkey-patch torch.from_numpy to work around numpy 1.x / torch 2.5 ABI
# mismatch.  PyTorch 2.5 wheels are compiled against the numpy 2.x C ABI,
# but Isaac Sim pins numpy < 2.  The mismatch causes torch.from_numpy() to
# raise ``TypeError: expected np.ndarray (got numpy.ndarray)``.
# We fall back to ``torch.as_tensor`` which copies the data but avoids the
# C-level type check.
# ---------------------------------------------------------------------------
try:
    import torch as _th
    import numpy as _np

    _orig_from_numpy = _th.from_numpy

    # Map numpy dtype to torch dtype for the fallback path
    _NP_TO_TORCH_DTYPE = {
        _np.float16: _th.float16, _np.float32: _th.float32, _np.float64: _th.float64,
        _np.int8: _th.int8, _np.int16: _th.int16, _np.int32: _th.int32, _np.int64: _th.int64,
        _np.uint8: _th.uint8, _np.bool_: _th.bool,
    }

    def _patched_from_numpy(ndarray):
        try:
            return _orig_from_numpy(ndarray)
        except TypeError:
            arr = _np.ascontiguousarray(ndarray)
            torch_dtype = _NP_TO_TORCH_DTYPE.get(arr.dtype.type, _th.float32)
            if arr.size == 0:
                return _th.empty(arr.shape, dtype=torch_dtype)
            # Use frombuffer to share memory without the numpy ABI check
            t = _th.frombuffer(arr, dtype=torch_dtype).reshape(arr.shape)
            # Keep a reference so numpy doesn't free the memory
            t.__numpy_ref = arr
            return t

    _th.from_numpy = _patched_from_numpy

    # Also patch Tensor.numpy() — the reverse direction has the same ABI issue.
    # trimesh calls np.asanyarray(tensor) which triggers tensor.__array__() ->
    # tensor.numpy() and fails with "Cannot interpret dtype('float64')".
    _TORCH_TO_NP_DTYPE = {v: k for k, v in _NP_TO_TORCH_DTYPE.items()}
    _orig_tensor_numpy = _th.Tensor.numpy

    def _patched_tensor_numpy(self, *, force=False):
        try:
            return _orig_tensor_numpy(self, force=force)
        except (TypeError, RuntimeError):
            t = self.detach().cpu() if self.requires_grad or not self.is_cpu else self
            if not self.is_cpu:
                t = self.detach().cpu()
            np_dtype = _TORCH_TO_NP_DTYPE.get(t.dtype, _np.float32)
            if t.numel() == 0:
                return _np.empty(tuple(t.shape), dtype=np_dtype)
            return _np.frombuffer(
                t.untyped_storage(), dtype=np_dtype, count=t.numel(),
                offset=t.storage_offset() * t.element_size(),
            ).reshape(tuple(t.shape))

    _th.Tensor.numpy = _patched_tensor_numpy
except Exception:
    pass
# ---------------------------------------------------------------------------

from omnigibson.controllers import REGISTERED_CONTROLLERS
from omnigibson.envs import Environment, VectorEnvironment
from omnigibson.macros import gm
from omnigibson.objects import REGISTERED_OBJECTS
from omnigibson.robots import REGISTERED_ROBOTS
from omnigibson.scenes import REGISTERED_SCENES
from omnigibson.sensors import ALL_SENSOR_MODALITIES
from omnigibson.simulator import _launch_simulator as launch
from omnigibson.tasks import REGISTERED_TASKS


# Create logger
RESET = "\033[0m"


class LogFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[32m",  # green
        logging.INFO: RESET,
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[31m" + "\033[1m",  # bold red
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, RESET)
        total_seconds = record.relativeCreated / 1000.0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        # Format as HH:MM:SS.sss, with leading zeros
        record.relativeCreated_hms = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
        return f"{color}{super().format(record)}{RESET}"


formatter = LogFormatter("[%(relativeCreated_hms)s] [%(levelname)s] [%(name)s] %(message)s")
logging.basicConfig()
logging.root.handlers[0].setFormatter(formatter)
log = logging.getLogger(__name__)

builtins.ISAAC_LAUNCHED_FROM_JUPYTER = (
    os.getenv("ISAAC_JUPYTER_KERNEL") is not None
)  # We set this in the kernel.json file

__version__ = "3.7.2"

root_path = os.path.dirname(os.path.realpath(__file__))

# Store paths to example configs
# TODO: Move this elsewhere.
example_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "configs")

# Initialize global variables
app = None  # (this is a singleton so it's okay that it's global)
sim = None  # (this is a singleton so it's okay that it's global)


# Create and expose a temporary directory for any use cases. It will get destroyed upon omni
# shutdown by the shutdown function.
tempdir = tempfile.mkdtemp()


def clear(
    gravity=None,
    physics_dt=None,
    rendering_dt=None,
    sim_step_dt=None,
    viewer_width=None,
    viewer_height=None,
    device=None,
):
    """
    Clear the stage and then call launch again to make og.sim point to a new simulator instance

    Args:
        gravity (None or float): gravity on z direction.
        physics_dt (None or float): dt between physics steps.
            If None, will use the current simulator value
        rendering_dt (None or float): dt between rendering steps. Note: rendering means rendering a frame of the
            current application and not only rendering a frame to the viewports/ cameras. So UI elements of
            Isaac Sim will be refreshed with this dt as well if running non-headless.
            If None, will use the current simulator value
        sim_step_dt (None or float): dt between self.step() calls. This is the amount of simulation time that
            passes every time step() is called. Note: This must be a multiple of @rendering_dt. If None, will
            use the current simulator value
        viewer_width (None or int): width of the camera image, in pixels
            If None, will use the current simulator value
        viewer_height (None or int): height of the camera image, in pixels
            If None, will use the current simulator value
        device (None or str): specifies the device to be used if running on the gpu with torch backend
            If None, will use the current simulator value

    """
    global sim

    import omnigibson.lazy as lazy

    # First save important simulator settings
    init_kwargs = dict(
        gravity=sim.gravity if gravity is None else gravity,
        physics_dt=sim.get_physics_dt() if physics_dt is None else physics_dt,
        rendering_dt=sim.get_rendering_dt() if rendering_dt is None else rendering_dt,
        sim_step_dt=sim.get_sim_step_dt() if sim_step_dt is None else sim_step_dt,
        viewer_width=sim.viewer_width if viewer_width is None else viewer_width,
        viewer_height=sim.viewer_height if viewer_height is None else viewer_height,
        device=sim.device if device is None else device,
    )

    # First let the simulator clear everything it owns.
    sim._partial_clear()

    # Then close the stage and remove pointers to the simulator object.
    assert lazy.isaacsim.core.utils.stage.close_stage()
    sim = None
    lazy.isaacsim.core.api.SimulationContext.clear_instance()

    # Then relaunch the simulator.
    launch(**init_kwargs)

    # Check that the device remains the same
    assert (
        sim.device == init_kwargs["device"]
    ), f"Device changed from {init_kwargs['device']} to {sim.device} after clear."


def cleanup(*args, **kwargs):
    # TODO: Currently tempfile removal will fail due to CopyPrim command (for example, GranularSystem in dicing_apple example.)
    try:
        shutil.rmtree(tempdir)
    except PermissionError:
        log.info("Permission error when removing temp files. Ignoring")
    from omnigibson.simulator import logo_small

    log.info(f"{'-' * 10} Shutting Down {logo_small()} {'-' * 10}")


def shutdown(due_to_signal=False):
    if app is not None:
        # If Isaac is running, we do the cleanup in its shutdown callback to avoid open handles.
        # TODO: Automated cleanup in callback doesn't work for some reason. Need to investigate.
        # Manually call cleanup for now.
        cleanup()
        app.close()
    else:
        # Otherwise, we do the cleanup here.
        cleanup()

        # If we're not shutting down due to a signal, we need to manually exit
        if not due_to_signal:
            exit(0)


def shutdown_handler(*args, **kwargs):
    shutdown(due_to_signal=True)
    return signal.default_int_handler(*args, **kwargs)


# Something somewhere disables the default SIGINT handler, so we need to re-enable it
signal.signal(signal.SIGINT, shutdown_handler)

__all__ = [
    "ALL_SENSOR_MODALITIES",
    "app",
    "cleanup",
    "clear",
    "Environment",
    "example_config_path",
    "gm",
    "launch",
    "log",
    "REGISTERED_CONTROLLERS",
    "REGISTERED_OBJECTS",
    "REGISTERED_ROBOTS",
    "REGISTERED_SCENES",
    "REGISTERED_TASKS",
    "shutdown",
    "sim",
    "tempdir",
    "VectorEnvironment",
]
