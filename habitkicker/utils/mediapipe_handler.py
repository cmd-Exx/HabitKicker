"""Class for handling MediaPipe initialization and processing"""

import mediapipe as mp

class MediapipeHandler:
    def __init__(self):
        self.CONFIDENCE = 0.7
        self._initialize_mediapipe()

    def _initialize_mediapipe(self):
        """Initialize all MediaPipe solutions"""
        self.mp_hands = mp.solutions.hands
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        self.hands = self.mp_hands.Hands(
            min_detection_confidence = self.CONFIDENCE,
            min_tracking_confidence = self.CONFIDENCE
        )
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            min_detection_confidence = self.CONFIDENCE,
            min_tracking_confidence = self.CONFIDENCE
        )
        self.pose = self.mp_pose.Pose(
            min_detection_confidence = self.CONFIDENCE,
            min_tracking_confidence = self.CONFIDENCE,
            model_complexity = 1  # Use medium complexity for better accuracy
        )