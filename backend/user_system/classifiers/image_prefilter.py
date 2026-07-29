"""Local, zero-API image pre-filter for nudity and gore (issue #393).

Runs blunt local detectors for the two most objective image violations —
nudity (rule 2, via NudeNet) and gore (rule 4, via an optional ONNX NSFW/gore
model) — inside the classification worker, before the paid AI vision cascade.
A confident hit is a final, non-appealable rejection, mirroring the text
pre-filter (`prefilter.py`); anything subtler is the cascade's job.

**Fail open.** The detector models are heavy *optional* dependencies
(`backend/requirements-local-image-filter.txt`). If a model is not installed,
not provisioned, or errors at inference time, the corresponding check yields a
score of 0.0 and the pre-filter allows the image — the AI cascade remains the
real gate. A missing local model must never reject a post on its own, and must
never block CI/dev where the models are absent. Availability is cached so a
missing dependency is not re-probed (or re-logged) on every image.

The two detector entry points — `_detect_nudity` and `_detect_gore` — return a
plain float score and are the seam tests patch; they never need the real models.
"""
import logging
import os
import tempfile

from .classifier_constants import (
    NUDENET_BLOCKING_CLASSES,
    LOCAL_NUDITY_THRESHOLD, LOCAL_GORE_THRESHOLD,
    ENV_GORE_MODEL_PATH, ENV_NUDENET_MODEL_PATH,
)
from .classifier_utils import ClassificationResult

logger = logging.getLogger(__name__)

# Lazily-initialised singletons, two vars per detector:
#   _*_detector / _*_session — None until loaded, then the loaded model object.
#   _*_unavailable          — False until a load is attempted and fails, then
#                             True so we neither retry the load nor re-log the
#                             failure on every image (preserving fail-open).
_nudenet_detector = None
_nudenet_unavailable = False
_gore_session = None          # onnxruntime.InferenceSession
_gore_unavailable = False

# Documented input contract for the optional gore ONNX model: a single
# float32 NCHW RGB tensor normalised to [0, 1]. The image is resized to this
# square; the model's output is read as an "unsafe" probability (its maximum
# element). A model with different preprocessing needs its own adapter.
_GORE_INPUT_SIZE = 224


def _get_nudenet():
    """Return a cached NudeDetector, or None if NudeNet is unavailable."""
    global _nudenet_detector, _nudenet_unavailable
    if _nudenet_unavailable:
        return None
    if _nudenet_detector is None:
        try:
            from nudenet import NudeDetector
            model_path = os.environ.get(ENV_NUDENET_MODEL_PATH)
            _nudenet_detector = NudeDetector(model_path=model_path) if model_path else NudeDetector()
            logger.info("Local image pre-filter: NudeNet loaded (model_path=%s).", model_path or 'bundled')
        except Exception:
            logger.warning("Local image pre-filter: NudeNet unavailable; nudity check disabled "
                           "(fails open). Install backend/requirements-local-image-filter.txt to enable it.",
                           exc_info=True)
            _nudenet_unavailable = True
            return None
    return _nudenet_detector


def _pil_to_temp_file(image):
    """Write ``image`` to a temp PNG and return its path (caller unlinks).

    NudeNet's detect() reads from a path across versions, which sidesteps any
    numpy/cv2 array-format coupling.
    """
    fd, path = tempfile.mkstemp(suffix='.png', prefix='prefilter_')
    os.close(fd)
    try:
        image.convert('RGB').save(path, format='PNG')
    except Exception:
        # save() failed (disk full, encoder error, ...): the caller never gets
        # the path, so unlink here rather than orphan the mkstemp file.
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _detect_nudity(image):
    """Max NudeNet confidence over the blocking classes, in [0, 1].

    Returns 0.0 when NudeNet is unavailable (fail open). Raising is fine too:
    prefilter_image treats any detector error as 0.0.
    """
    detector = _get_nudenet()
    if detector is None:
        return 0.0
    path = _pil_to_temp_file(image)
    try:
        detections = detector.detect(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    scores = [d.get('score', 0.0) for d in (detections or [])
              if d.get('class') in NUDENET_BLOCKING_CLASSES]
    return max(scores, default=0.0)


def _get_gore_session():
    """Return a cached onnxruntime session for the gore model, or None.

    None (skip, fail open) when no model path is configured or onnxruntime is
    unavailable — there is no reliable pip-installable local gore model, so the
    operator provisions one and points LOCAL_GORE_MODEL_PATH at it.
    """
    global _gore_session, _gore_unavailable
    if _gore_unavailable:
        return None
    if _gore_session is None:
        model_path = os.environ.get(ENV_GORE_MODEL_PATH)
        if not model_path:
            _gore_unavailable = True
            return None
        try:
            import onnxruntime
            _gore_session = onnxruntime.InferenceSession(
                model_path, providers=['CPUExecutionProvider'])
            logger.info("Local image pre-filter: gore ONNX model loaded from %s.", model_path)
        except Exception:
            logger.warning("Local image pre-filter: gore model at %s could not be loaded; "
                           "gore check disabled (fails open).", model_path, exc_info=True)
            _gore_unavailable = True
            return None
    return _gore_session


def _detect_gore(image):
    """Gore/unsafe probability in [0, 1] from the optional ONNX model.

    Returns 0.0 when no gore model is configured/available (fail open). The
    model is fed a normalised NCHW RGB tensor (see _GORE_INPUT_SIZE) and its
    output's maximum element is read as the unsafe probability.
    """
    session = _get_gore_session()
    if session is None:
        return 0.0
    import numpy as np
    resized = image.convert('RGB').resize((_GORE_INPUT_SIZE, _GORE_INPUT_SIZE))
    tensor = np.asarray(resized, dtype=np.float32) / 255.0      # HWC, [0,1]
    tensor = tensor.transpose(2, 0, 1)[np.newaxis, ...]          # NCHW
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: tensor})
    return float(np.max(outputs[0]))


def prefilter_image(image):
    """Local heuristic check for blatant nudity/gore; never calls an LLM.

    Returns a ClassificationResult: a final, non-appealable rejection on a
    confident nudity or gore hit (nudity is checked first), or allowed=True
    when nothing blatant was found (the AI cascade still runs). Any detector
    error is swallowed and treated as "no hit", so the pre-filter can only ever
    add a rejection the cascade might also have made — never fail a post shut
    on infrastructure grounds.
    """
    try:
        nudity_score = _detect_nudity(image)
    except Exception:
        logger.warning("Local image pre-filter: nudity detection errored; treating as no hit.", exc_info=True)
        nudity_score = 0.0
    if nudity_score >= LOCAL_NUDITY_THRESHOLD:
        logger.info("Local image pre-filter: nudity hit (score=%.2f >= %.2f); final rejection.",
                    nudity_score, LOCAL_NUDITY_THRESHOLD)
        return ClassificationResult(allowed=False, appealable=False, reason_code='nudity')

    try:
        gore_score = _detect_gore(image)
    except Exception:
        logger.warning("Local image pre-filter: gore detection errored; treating as no hit.", exc_info=True)
        gore_score = 0.0
    if gore_score >= LOCAL_GORE_THRESHOLD:
        logger.info("Local image pre-filter: gore hit (score=%.2f >= %.2f); final rejection.",
                    gore_score, LOCAL_GORE_THRESHOLD)
        return ClassificationResult(allowed=False, appealable=False, reason_code='gore')

    return ClassificationResult(allowed=True)
