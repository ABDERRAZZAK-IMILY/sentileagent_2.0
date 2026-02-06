#!/usr/bin/env python3
"""
SentinelAgent Iris Service
Biometric authentication service using iris recognition
"""

import os
import base64
import io
import logging
from datetime import datetime

import numpy as np
import cv2
from PIL import Image
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from iris_utils import extract_iris_features_from_frame, detect_eye_position

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": os.environ.get('CORS_ORIGINS', '*').split(','),
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configuration
THRESHOLD = float(os.environ.get('THRESHOLD', '0.85'))
FEATURES_FILE = os.environ.get('FEATURES_FILE', '/app/data/stored_features.npy')
SPRING_BOOT_URL = os.environ.get('SPRING_BOOT_URL', 'http://localhost:8080')
IRIS_SERVICE_SECRET = os.environ.get('IRIS_SERVICE_SECRET', 'InternalSecretKeyForIrisService_998877')

# In-memory storage for multiple users (user_id -> features)
enrolled_users = {}


def load_enrolled_features():
    """Load enrolled iris features from file"""
    global enrolled_users
    try:
        if os.path.exists(FEATURES_FILE):
            enrolled_users = np.load(FEATURES_FILE, allow_pickle=True).item()
            if not isinstance(enrolled_users, dict):
                enrolled_users = {'default': enrolled_users}
            logger.info(f"Loaded {len(enrolled_users)} enrolled user(s)")
            return True
    except Exception as e:
        logger.error(f"Error loading features: {e}")
    enrolled_users = {}
    return False


def save_enrolled_features():
    """Save enrolled iris features to file"""
    try:
        np.save(FEATURES_FILE, enrolled_users)
        logger.info(f"Saved {len(enrolled_users)} enrolled user(s)")
        return True
    except Exception as e:
        logger.error(f"Error saving features: {e}")
        return False


def decode_image(data):
    """Decode base64 image data to OpenCV frame"""
    try:
        image_bytes = base64.b64decode(data)
        image = Image.open(io.BytesIO(image_bytes))
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.error(f"Image decode error: {e}")
        return None


# ============================================
# HTTP Routes
# ============================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'iris-service',
        'timestamp': datetime.utcnow().isoformat(),
        'enrolled_users': len(enrolled_users),
        'threshold': THRESHOLD
    })


@app.route('/api/v1/iris/status', methods=['GET'])
def get_status():
    """Get iris service status"""
    return jsonify({
        'enrolled_users': len(enrolled_users),
        'threshold': THRESHOLD,
        'features_file_exists': os.path.exists(FEATURES_FILE)
    })


@app.route('/api/v1/iris/enroll', methods=['POST'])
def http_enroll():
    """HTTP endpoint for iris enrollment"""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': 'No image provided'}), 400

        user_id = data.get('user_id', 'default')
        frame = decode_image(data['image'])
        
        if frame is None:
            return jsonify({'success': False, 'error': 'Invalid image data'}), 400

        features = extract_iris_features_from_frame(frame)
        if features is None:
            return jsonify({
                'success': False, 
                'error': 'No eye detected. Please position your eye correctly.'
            }), 400

        enrolled_users[user_id] = features
        save_enrolled_features()
        
        logger.info(f"User '{user_id}' enrolled successfully")
        return jsonify({
            'success': True, 
            'message': 'Iris enrolled successfully!',
            'user_id': user_id
        })

    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/iris/authenticate', methods=['POST'])
def http_authenticate():
    """HTTP endpoint for iris authentication"""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'authenticated': False, 'error': 'No image provided'}), 400

        user_id = data.get('user_id', 'default')
        
        if user_id not in enrolled_users:
            return jsonify({
                'authenticated': False, 
                'error': f'No iris enrolled for user: {user_id}'
            }), 400

        frame = decode_image(data['image'])
        if frame is None:
            return jsonify({'authenticated': False, 'error': 'Invalid image data'}), 400

        features = extract_iris_features_from_frame(frame)
        if features is None:
            return jsonify({
                'authenticated': False, 
                'error': 'No eye detected. Please position your eye correctly.'
            }), 400

        stored_features = enrolled_users[user_id]
        similarity = np.dot(features, stored_features) / (
            np.linalg.norm(features) * np.linalg.norm(stored_features)
        )

        authenticated = similarity >= THRESHOLD
        
        logger.info(f"Authentication attempt for '{user_id}': {authenticated} (similarity: {similarity:.4f})")
        
        return jsonify({
            'authenticated': authenticated,
            'similarity': float(similarity),
            'threshold': THRESHOLD,
            'user_id': user_id
        })

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return jsonify({'authenticated': False, 'error': str(e)}), 500


@app.route('/api/v1/iris/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete enrolled user"""
    if user_id in enrolled_users:
        del enrolled_users[user_id]
        save_enrolled_features()
        logger.info(f"User '{user_id}' deleted")
        return jsonify({'success': True, 'message': f'User {user_id} deleted'})
    return jsonify({'success': False, 'error': 'User not found'}), 404


# ============================================
# WebSocket Events
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'status': 'connected', 'service': 'iris-service'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('detect_eye')
def handle_detect_eye(data):
    """Detect eye position for live preview"""
    try:
        frame = decode_image(data)
        if frame is None:
            emit('eye_position', {'detected': False, 'error': 'Invalid image'})
            return

        result = detect_eye_position(frame)
        if result is None:
            emit('eye_position', {'detected': False})
        else:
            face_box, eye_box, eye_image_b64 = result
            emit('eye_position', {
                'detected': True,
                'face': {
                    'x': int(face_box[0]),
                    'y': int(face_box[1]),
                    'width': int(face_box[2]),
                    'height': int(face_box[3])
                },
                'eye': {
                    'x': int(eye_box[0]),
                    'y': int(eye_box[1]),
                    'width': int(eye_box[2]),
                    'height': int(eye_box[3])
                },
                'eyeImage': eye_image_b64
            })
    except Exception as e:
        logger.error(f"Eye detection error: {e}")
        emit('eye_position', {'detected': False, 'error': str(e)})


@socketio.on('iris_enroll')
def handle_iris_enroll(data):
    """Handle iris enrollment via WebSocket"""
    try:
        user_id = data.get('user_id', 'default')
        frame = decode_image(data['image'])
        
        if frame is None:
            emit('enroll_result', {'success': False, 'error': 'Invalid image data'})
            return

        features = extract_iris_features_from_frame(frame)
        if features is None:
            emit('enroll_result', {
                'success': False, 
                'error': 'No eye detected. Please position your eye correctly.'
            })
            return

        enrolled_users[user_id] = features
        save_enrolled_features()
        
        logger.info(f"User '{user_id}' enrolled via WebSocket")
        emit('enroll_result', {
            'success': True, 
            'message': 'Iris enrolled successfully!',
            'user_id': user_id
        })

    except Exception as e:
        logger.error(f"WebSocket enrollment error: {e}")
        emit('enroll_result', {'success': False, 'error': str(e)})


@socketio.on('iris_frame')
def handle_iris_frame(data):
    """Handle iris authentication via WebSocket"""
    try:
        user_id = data.get('user_id', 'default')
        
        if user_id not in enrolled_users:
            emit('iris_result', {
                'authenticated': False, 
                'error': f'No iris enrolled for user: {user_id}'
            })
            return

        frame = decode_image(data['image'])
        if frame is None:
            emit('iris_result', {'authenticated': False, 'error': 'Invalid image data'})
            return

        features = extract_iris_features_from_frame(frame)
        if features is None:
            emit('iris_result', {
                'authenticated': False, 
                'error': 'No eye detected. Please position your eye correctly.'
            })
            return

        stored_features = enrolled_users[user_id]
        similarity = np.dot(features, stored_features) / (
            np.linalg.norm(features) * np.linalg.norm(stored_features)
        )

        authenticated = similarity >= THRESHOLD
        
        logger.info(f"WebSocket auth for '{user_id}': {authenticated} (similarity: {similarity:.4f})")
        
        emit('iris_result', {
            'authenticated': authenticated,
            'similarity': float(similarity),
            'threshold': THRESHOLD,
            'user_id': user_id
        })

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        emit('iris_result', {'authenticated': False, 'error': str(e)})


# ============================================
# Main
# ============================================

if __name__ == '__main__':
    # Load existing features on startup
    load_enrolled_features()
    
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Iris Service on {host}:{port}")
    logger.info(f"Threshold: {THRESHOLD}")
    logger.info(f"Features file: {FEATURES_FILE}")
    
    socketio.run(app, host=host, port=port, debug=debug)
