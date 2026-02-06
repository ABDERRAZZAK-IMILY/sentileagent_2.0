#!/usr/bin/env python3
"""
SentinelAgent Iris Recognition Utilities
Advanced iris feature extraction and eye detection
"""

import base64
import io
import logging

import numpy as np
import cv2
from PIL import Image
from scipy import ndimage

logger = logging.getLogger(__name__)

# Haar cascades for face and eye detection
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

# Iris detection parameters
IRIS_RADIUS_RANGE = (10, 40)
PUPIL_RADIUS_RANGE = (5, 20)


def detect_eye_position(frame):
    """
    Detect eye position in the frame
    
    Returns:
        tuple: (face_box, eye_box, eye_image_base64) or None if no eye detected
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Detect faces
    faces = FACE_CASCADE.detectMultiScale(
        gray, 
        scaleFactor=1.1, 
        minNeighbors=5, 
        minSize=(100, 100)
    )
    
    if len(faces) == 0:
        return None
    
    # Use the largest face
    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face
    
    # Extract face region
    face_roi_gray = gray[fy:fy+fh, fx:fx+fw]
    
    # Detect eyes within face region
    eyes = EYE_CASCADE.detectMultiScale(
        face_roi_gray,
        scaleFactor=1.1,
        minNeighbors=3,
        minSize=(30, 30)
    )
    
    if len(eyes) == 0:
        return None
    
    # Use the largest eye
    eye = max(eyes, key=lambda e: e[2] * e[3])
    ex, ey, ew, eh = eye
    
    # Adjust eye coordinates to frame
    eye_abs = (fx + ex, fy + ey, ew, eh)
    
    # Extract eye image
    eye_roi = frame[fy+ey:fy+ey+eh, fx+ex:fx+ex+ew]
    
    # Convert to base64 for transmission
    _, buffer = cv2.imencode('.png', eye_roi)
    eye_b64 = base64.b64encode(buffer).decode('utf-8')
    
    return (face, eye_abs, eye_b64)


def detect_pupil(eye_roi):
    """
    Detect pupil center and radius in eye ROI
    
    Returns:
        tuple: (center_x, center_y, radius) or None
    """
    gray = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2GRAY) if len(eye_roi.shape) == 3 else eye_roi
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    
    # Detect circles (pupil)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=eye_roi.shape[0] // 4,
        param1=50,
        param2=30,
        minRadius=PUPIL_RADIUS_RANGE[0],
        maxRadius=PUPIL_RADIUS_RANGE[1]
    )
    
    if circles is not None:
        # Return the strongest circle detection
        circles = np.uint16(np.around(circles))
        return circles[0][0]  # x, y, radius
    
    return None


def detect_iris_boundary(eye_roi, pupil_center, pupil_radius):
    """
    Detect iris outer boundary
    
    Returns:
        int: Iris radius or estimated radius
    """
    gray = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2GRAY) if len(eye_roi.shape) == 3 else eye_roi
    
    # Create mask excluding pupil
    mask = np.ones_like(gray) * 255
    cv2.circle(mask, (pupil_center[0], pupil_center[1]), pupil_radius + 5, 0, -1)
    
    # Apply mask
    masked = cv2.bitwise_and(gray, mask)
    
    # Detect outer iris circle
    circles = cv2.HoughCircles(
        masked,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=eye_roi.shape[0] // 2,
        param1=30,
        param2=20,
        minRadius=pupil_radius + 10,
        maxRadius=min(pupil_radius + 30, IRIS_RADIUS_RANGE[1])
    )
    
    if circles is not None:
        circles = np.uint16(np.around(circles))
        return circles[0][2]
    
    # Estimate iris radius if detection fails
    return min(pupil_radius + 15, IRIS_RADIUS_RANGE[1])


def normalize_iris(eye_roi, pupil_center, pupil_radius, iris_radius):
    """
    Normalize iris to rectangular format using Daugman's rubber sheet model
    
    Returns:
        numpy.ndarray: Normalized iris image
    """
    height = 64
    width = 512
    
    normalized = np.zeros((height, width), dtype=np.uint8)
    
    for y in range(height):
        for x in range(width):
            # Map polar coordinates to cartesian
            theta = 2 * np.pi * x / width
            r = pupil_radius + (iris_radius - pupil_radius) * y / height
            
            px = int(pupil_center[0] + r * np.cos(theta))
            py = int(pupil_center[1] + r * np.sin(theta))
            
            if 0 <= px < eye_roi.shape[1] and 0 <= py < eye_roi.shape[0]:
                if len(eye_roi.shape) == 3:
                    normalized[y, x] = eye_roi[py, px, 0]
                else:
                    normalized[y, x] = eye_roi[py, px]
    
    return normalized


def extract_iris_features(normalized_iris):
    """
    Extract features from normalized iris using Gabor filters
    
    Returns:
        numpy.ndarray: Feature vector
    """
    features = []
    
    # Apply Gabor filters at different scales and orientations
    scales = [4, 8, 16]
    orientations = [0, np.pi/4, np.pi/2, 3*np.pi/4]
    
    for scale in scales:
        for theta in orientations:
            # Create Gabor kernel
            kernel = cv2.getGaborKernel(
                (scale * 2 + 1, scale * 2 + 1),
                sigma=scale,
                theta=theta,
                lambd=scale * 2,
                gamma=0.5,
                psi=0
            )
            
            # Apply filter
            filtered = cv2.filter2D(normalized_iris, cv2.CV_64F, kernel)
            
            # Extract statistics as features
            features.extend([
                np.mean(filtered),
                np.std(filtered),
                np.max(filtered),
                np.min(filtered)
            ])
    
    # Add histogram features
    hist = cv2.calcHist([normalized_iris], [0], None, [16], [0, 256])
    features.extend(hist.flatten())
    
    return np.array(features, dtype=np.float32)


def extract_iris_features_from_frame(frame):
    """
    Complete iris feature extraction pipeline from frame
    
    Args:
        frame: OpenCV BGR image
        
    Returns:
        numpy.ndarray: Feature vector or None if extraction fails
    """
    try:
        # Detect eye position
        result = detect_eye_position(frame)
        if result is None:
            return None
        
        face_box, eye_box, _ = result
        ex, ey, ew, eh = eye_box
        
        # Extract eye ROI
        eye_roi = frame[ey:ey+eh, ex:ex+ew]
        
        # Detect pupil
        pupil = detect_pupil(eye_roi)
        if pupil is None:
            # Fallback: use center of eye ROI
            pupil = (ew // 2, eh // 2, min(ew, eh) // 6)
        
        pupil_center = (pupil[0], pupil[1])
        pupil_radius = pupil[2]
        
        # Detect iris boundary
        iris_radius = detect_iris_boundary(eye_roi, pupil_center, pupil_radius)
        
        # Normalize iris
        normalized = normalize_iris(eye_roi, pupil_center, pupil_radius, iris_radius)
        
        # Enhance contrast
        normalized = cv2.equalizeHist(normalized)
        
        # Extract features
        features = extract_iris_features(normalized)
        
        # Normalize feature vector
        features = features / (np.linalg.norm(features) + 1e-8)
        
        return features
        
    except Exception as e:
        logger.error(f"Feature extraction error: {e}")
        return None


def compare_iris_features(features1, features2):
    """
    Compare two iris feature vectors
    
    Returns:
        float: Similarity score (0-1)
    """
    # Cosine similarity
    similarity = np.dot(features1, features2) / (
        np.linalg.norm(features1) * np.linalg.norm(features2) + 1e-8
    )
    
    return float(similarity)


# Test function
if __name__ == '__main__':
    # Test with sample image if provided
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        frame = cv2.imread(image_path)
        
        if frame is not None:
            features = extract_iris_features_from_frame(frame)
            if features is not None:
                print(f"Features extracted: {len(features)} dimensions")
                print(f"Feature vector (first 10): {features[:10]}")
            else:
                print("Failed to extract features")
        else:
            print(f"Could not load image: {image_path}")
    else:
        print("Usage: python iris_utils.py <image_path>")
