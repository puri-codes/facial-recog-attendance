"""
Face recognition utilities using OpenCV and face_recognition library.
Provides face detection, encoding, and matching functions.
"""
import numpy as np
import warnings

warnings.filterwarnings(
    'ignore',
    message='pkg_resources is deprecated as an API.*',
    category=UserWarning,
)

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def _normalize_image_array(image_array):
    """
    Normalize images to (H, W, 3) uint8 contiguous arrays for dlib bindings.
    """
    if image_array is None:
        return None

    arr = np.asarray(image_array)

    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[:, :, :3]
    elif arr.ndim != 3 or arr.shape[2] != 3:
        return None

    if arr.dtype != np.uint8:
        if np.issubdtype(arr.dtype, np.floating):
            scale = 255.0 if arr.size and arr.max() <= 1.0 else 1.0
            arr = np.clip(arr * scale, 0, 255).astype(np.uint8)
        else:
            arr = np.clip(arr, 0, 255).astype(np.uint8)

    return np.ascontiguousarray(arr)


def _bgr_to_rgb(image_array):
    """Convert OpenCV-style BGR image to RGB with contiguous memory."""
    if OPENCV_AVAILABLE:
        return cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
    return image_array[:, :, ::-1].copy()


def encode_face_from_image(image_path):
    """
    Generate 128-d face encoding from an image file.
    Returns numpy array or None if no face found.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None

    image = _normalize_image_array(face_recognition.load_image_file(image_path))
    if image is None:
        return None

    try:
        encodings = face_recognition.face_encodings(image)
    except Exception:
        return None

    if encodings:
        return encodings[0]
    return None


def encode_face_from_array(image_array):
    """
    Generate face encoding from a numpy array.
    Automatically handles both BGR (OpenCV) and RGB formats.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None

    normalized = _normalize_image_array(image_array)
    if normalized is None:
        return None

    # Detect and convert color space properly
    # If the normalized array came from OpenCV (BGR), convert to RGB
    # If it came from PIL or other source (already RGB), use as-is
    # To be safe, we assume OpenCV format (BGR) and convert
    rgb = _bgr_to_rgb(normalized)
    
    try:
        encodings = face_recognition.face_encodings(rgb)
    except Exception:
        return None

    if encodings:
        return encodings[0]
    return None


def detect_faces(image_array):
    """
    Detect faces in an image and return bounding boxes in consistent (top, right, bottom, left) format.
    Returns list of (top, right, bottom, left) tuples.
    """
    normalized = _normalize_image_array(image_array)
    if normalized is None:
        return []

    if not FACE_RECOGNITION_AVAILABLE:
        # Fallback to OpenCV Haar cascade - normalized is BGR format
        if not OPENCV_AVAILABLE:
            return []
        gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        # Convert from (x, y, w, h) to (top, right, bottom, left) format for consistency
        return [(y, x + w, y + h, x) for (x, y, w, h) in faces]

    # Use face_recognition library - expects RGB
    rgb = _bgr_to_rgb(normalized)
    try:
        locations = face_recognition.face_locations(rgb)
        # face_recognition returns (top, right, bottom, left) - already correct format
        return locations
    except Exception:
        return []


def match_face(unknown_encoding, known_encodings, known_ids, tolerance=0.5):
    """
    Match an unknown face encoding against a list of known encodings.

    Args:
        unknown_encoding: numpy array of the unknown face
        known_encodings: list of numpy arrays
        known_ids: list of IDs corresponding to known_encodings
        tolerance: how strict the matching is (lower = stricter)

    Returns:
        (matched_id, confidence) or (None, 0.0)
    """
    if not FACE_RECOGNITION_AVAILABLE or not known_encodings:
        return None, 0.0

    distances = face_recognition.face_distance(known_encodings, unknown_encoding)

    if len(distances) == 0:
        return None, 0.0

    best_idx = np.argmin(distances)
    best_distance = distances[best_idx]

    if best_distance <= tolerance:
        confidence = round((1.0 - best_distance) * 100, 2)
        return known_ids[best_idx], confidence

    return None, 0.0


def decode_base64_image(base64_string):
    """
    Decode a base64-encoded image string to numpy array in BGR format (OpenCV compatible).
    Ensures consistent color space regardless of decoding method used.
    """
    import base64

    if not base64_string:
        return None

    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]

    if not base64_string.strip():
        return None

    image_bytes = base64.b64decode(base64_string, validate=True)
    if not image_bytes:
        return None

    nparr = np.frombuffer(image_bytes, np.uint8)
    if nparr.size == 0:
        return None

    if OPENCV_AVAILABLE:
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # cv2.imdecode returns BGR format, which is what we want
        return image if image is not None else None

    # Fallback using PIL (returns RGB, so convert to BGR for consistency)
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes))
    rgb_array = np.array(img)
    
    # Convert RGB to BGR for consistency with OpenCV format
    if rgb_array.ndim == 3 and rgb_array.shape[2] == 3:
        return rgb_array[:, :, ::-1]  # RGB to BGR
    
    return rgb_array
