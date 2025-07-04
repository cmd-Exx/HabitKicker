"""Class for detecting slouching based on posture landmarks"""

import numpy as np
import cv2
import time
import os
import pickle

class SlouchDetector:
    def __init__(self, threshold_percentage):
        self.calibrated = False
        self.calibration_landmarks = None
        self.threshold_percentage = threshold_percentage
        self.calibration_countdown = 0
        self.calibration_start_time = 0
        self.calibration_duration = 3.0  # seconds
        
        # New variables for collecting posture data during calibration
        self.calibration_samples = []
        self.last_sample_time = 0
        self.sample_interval = 0.1  # Collect samples every 100 ms
        
        # Path for saving calibration data
        self.base_dir = os.getcwd()
        self.calibration_file = os.path.join(self.base_dir, "data", "posture_calibration.pkl")
        
        # Performance optimization: cache for calculations
        self.last_slouch_calculation_time = 0
        self.slouch_calculation_interval = 0.1  # Calculate slouch every 100ms
        self.last_slouch_percentage = 0
        self.last_slouch_detected = False
        
        # Try to load existing calibration data
        self.load_calibration()
        
    def start_calibration(self):
        """Start the calibration process"""
        self.calibrated = False
        self.calibration_landmarks = None
        self.calibration_countdown = 3  # 3 second countdown before calibration
        self.calibration_start_time = time.time()
        self.calibration_samples = []  # Reset samples
        
    def update_calibration(self, frame, pose_landmarks):
        """Update calibration process and draw UI elements"""
        current_time = time.time()
        
        # Handle countdown phase
        if self.calibration_countdown > 0:
            elapsed = current_time - self.calibration_start_time
            remaining = self.calibration_countdown - elapsed
            
            if remaining <= 0:
                # Countdown finished, start actual calibration
                self.calibration_countdown = 0
                self.calibration_start_time = current_time
                self.calibration_samples = []  # Reset samples
                self.last_sample_time = current_time
                return False
            
            return False
            
        # Handle actual calibration phase
        elapsed = current_time - self.calibration_start_time
        if elapsed < self.calibration_duration:      
            # Collect samples at regular intervals
            if current_time - self.last_sample_time >= self.sample_interval and pose_landmarks:
                self.last_sample_time = current_time
                landmarks = self._extract_posture_landmarks(pose_landmarks)
                if landmarks:
                    self.calibration_samples.append(landmarks)
                    
            return False
        else:
            # Calibration duration is complete
            # Make sure we collect the final sample if needed
            if pose_landmarks and len(self.calibration_samples) == 0:
                # If somehow we have no samples yet, get at least one
                landmarks = self._extract_posture_landmarks(pose_landmarks)
                if landmarks:
                    self.calibration_samples.append(landmarks)
            
            # Now complete the calibration
            if not self.calibrated and len(self.calibration_samples) > 0:
                self._complete_calibration()
                return True
            elif self.calibrated:
                # Already calibrated
                return True
            else:
                # No samples collected, keep trying
                print("Warning: No calibration samples collected yet, continuing...")
                self.calibration_start_time = current_time  # Reset timer to get more samples
                return False
    
    def _complete_calibration(self):
        """Complete the calibration process by averaging collected landmarks"""
        if len(self.calibration_samples) == 0:
            print("Warning: No calibration samples collected")
            return
            
        # Average all collected samples
        avg_landmarks = {}
        
        # Initialize with the structure of the first sample
        for key in self.calibration_samples[0].keys():
            # Each landmark has 3 coordinates (x, y, z)
            avg_landmarks[key] = [0, 0, 0]
        
        # Sum all samples
        for sample in self.calibration_samples:
            for key, coords in sample.items():
                for i in range(3):  # x, y, z
                    avg_landmarks[key][i] += coords[i]
        
        # Divide by number of samples to get average
        for key in avg_landmarks.keys():
            for i in range(3):  # x, y, z
                avg_landmarks[key][i] /= len(self.calibration_samples)
            
            # Convert lists back to tuples
            avg_landmarks[key] = tuple(avg_landmarks[key])
        
        # Store the averaged landmarks
        self.calibration_landmarks = avg_landmarks
        self.calibrated = True
        print(f"Calibration complete with {len(self.calibration_samples)} samples")
        
        # Save the calibration data
        self.save_calibration()
    
    def _extract_posture_landmarks(self, pose_landmarks):
        """Extract relevant landmarks for posture analysis"""
        # We're only interested in upper body landmarks (shoulders, neck, nose)
        landmarks = {}
        
        if hasattr(pose_landmarks, 'landmark'):
            # Extract shoulder landmarks (11 and 12 in MediaPipe Pose)
            landmarks['left_shoulder'] = (
                pose_landmarks.landmark[11].x,
                pose_landmarks.landmark[11].y,
                pose_landmarks.landmark[11].z
            )
            landmarks['right_shoulder'] = (
                pose_landmarks.landmark[12].x,
                pose_landmarks.landmark[12].y,
                pose_landmarks.landmark[12].z
            )
            
            # Extract neck landmark (mid-point between shoulders)
            landmarks['neck'] = (
                (pose_landmarks.landmark[11].x + pose_landmarks.landmark[12].x) / 2,
                (pose_landmarks.landmark[11].y + pose_landmarks.landmark[12].y) / 2,
                (pose_landmarks.landmark[11].z + pose_landmarks.landmark[12].z) / 2
            )
            
            # Nose landmark for vertical alignment
            landmarks['nose'] = (
                pose_landmarks.landmark[0].x,
                pose_landmarks.landmark[0].y,
                pose_landmarks.landmark[0].z
            )
            
            # Add ear landmarks for head tilt detection
            landmarks['left_ear'] = (
                pose_landmarks.landmark[7].x,
                pose_landmarks.landmark[7].y,
                pose_landmarks.landmark[7].z
            )
            landmarks['right_ear'] = (
                pose_landmarks.landmark[8].x,
                pose_landmarks.landmark[8].y,
                pose_landmarks.landmark[8].z
            )
            
        return landmarks
    
    def check_slouching(self, frame, pose_landmarks):
        """Check if the user is slouching based on calibrated posture"""
        if not self.calibrated or not pose_landmarks:
            return False
        
        current_time = time.time()
        
        # Only recalculate slouch at certain intervals to improve performance
        if current_time - self.last_slouch_calculation_time >= self.slouch_calculation_interval:
            current_landmarks = self._extract_posture_landmarks(pose_landmarks)
            
            # If we couldn't extract the necessary landmarks, return False
            if not current_landmarks or not self.calibration_landmarks:
                return False
            
            # Calculate slouch metrics
            self.last_slouch_detected, self.last_slouch_percentage = self._calculate_slouch(current_landmarks)
            self.last_slouch_calculation_time = current_time
        
        # Always draw the slouch percentage
        if self.last_slouch_detected:
            self._draw_slouch_alert(frame, self.last_slouch_percentage)
        else:
            self._draw_slouch_percentage(frame, self.last_slouch_percentage)
            
        return self.last_slouch_detected
    
    def _calculate_slouch(self, current_landmarks):
        """Calculate if the user is slouching and by how much"""
        # Calculate multiple slouch indicators
        
        # 1. Vertical change in shoulder position
        left_shoulder_y_diff = current_landmarks['left_shoulder'][1] - self.calibration_landmarks['left_shoulder'][1]
        right_shoulder_y_diff = current_landmarks['right_shoulder'][1] - self.calibration_landmarks['right_shoulder'][1]
        avg_shoulder_diff = (left_shoulder_y_diff + right_shoulder_y_diff) / 2
        
        # 2. Change in neck-to-nose angle
        # Calculate the angle between the neck-nose line in calibration vs current
        cal_neck_nose_vector = np.array([
            self.calibration_landmarks['nose'][0] - self.calibration_landmarks['neck'][0],
            self.calibration_landmarks['nose'][1] - self.calibration_landmarks['neck'][1]
        ])
        curr_neck_nose_vector = np.array([
            current_landmarks['nose'][0] - current_landmarks['neck'][0],
            current_landmarks['nose'][1] - current_landmarks['neck'][1]
        ])
        
        # Normalize vectors
        cal_neck_nose_norm = np.linalg.norm(cal_neck_nose_vector)
        curr_neck_nose_norm = np.linalg.norm(curr_neck_nose_vector)
        
        if cal_neck_nose_norm > 0 and curr_neck_nose_norm > 0:
            cal_neck_nose_vector = cal_neck_nose_vector / cal_neck_nose_norm
            curr_neck_nose_vector = curr_neck_nose_vector / curr_neck_nose_norm
            
            # Calculate dot product and angle
            dot_product = np.clip(np.dot(cal_neck_nose_vector, curr_neck_nose_vector), -1.0, 1.0)
            angle_diff = np.arccos(dot_product) * (180 / np.pi)  # Convert to degrees
        else:
            angle_diff = 0
        
        # 3. Calculate distance between nose and neck (shorter when slouching)
        # Use squared distance for better performance
        cal_nose_neck_dist_sq = self._squared_distance(
            self.calibration_landmarks['nose'][:2],  # Only use x,y coordinates
            self.calibration_landmarks['neck'][:2]
        )
        
        curr_nose_neck_dist_sq = self._squared_distance(
            current_landmarks['nose'][:2],
            current_landmarks['neck'][:2]
        )
        
        # Calculate distance ratio (less than 1 means slouching)
        # Take square root only once at the end for the ratio
        cal_nose_neck_dist = np.sqrt(cal_nose_neck_dist_sq) if cal_nose_neck_dist_sq > 0 else 0.001
        curr_nose_neck_dist = np.sqrt(curr_nose_neck_dist_sq) if curr_nose_neck_dist_sq > 0 else 0
        dist_ratio = curr_nose_neck_dist / cal_nose_neck_dist if cal_nose_neck_dist > 0 else 1
        
        # Combine metrics to calculate slouch percentage
        # Weight the metrics: shoulder position, angle change, distance ratio
        shoulder_factor = 0.8 # Vertical position of shoulders relative to calibrated position
        angle_factor =  0.1 # Head tilt angle
        distance_factor = 0.4 # Distance between nose and neck
        
        # Calculate reference distance for shoulder movement percentage
        ref_distance = abs(self.calibration_landmarks['nose'][1] - 
                          (self.calibration_landmarks['left_shoulder'][1] + 
                           self.calibration_landmarks['right_shoulder'][1]) / 2)
        
        shoulder_percentage = (avg_shoulder_diff / ref_distance) * 100 if ref_distance > 0 else 0
        angle_percentage = angle_diff * 2  # Scale angle difference to percentage
        distance_percentage = (1 - dist_ratio) * 100 if dist_ratio < 1 else 0
        
        # Combine metrics
        slouch_percentage = (
            shoulder_percentage * shoulder_factor + # Shoulder detection
            angle_percentage * angle_factor + # Neck angle detection
            distance_percentage * distance_factor # Nose-neck distance detection
        )
        
        # Detect slouching if the percentage exceeds the threshold
        slouch_detected = slouch_percentage > self.threshold_percentage
        
        return slouch_detected, slouch_percentage
    
    def _squared_distance(self, point1, point2):
        """Calculate squared Euclidean distance between two points"""
        # This is faster than np.linalg.norm as it avoids the square root
        dx = point1[0] - point2[0]
        dy = point1[1] - point2[1]
        return dx*dx + dy*dy
    
    def _draw_slouch_alert(self, frame, slouch_percentage):
        """Draw slouch alert on the frame"""
        h, w, _ = frame.shape
        
        # Draw alert text
        cv2.putText(
            frame, 
            f"Slouching: {int(slouch_percentage)}% (Threshold: {self.threshold_percentage}%)", 
            (50, 130), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (0, 0, 255), 
            2
        )
    
    def _draw_slouch_percentage(self, frame, slouch_percentage):
        """Draw slouch percentage on the frame when not slouching"""
        # Calculate color based on how close to threshold (green to yellow)
        ratio = min(slouch_percentage / self.threshold_percentage, 0.9)  # Cap at 90% of threshold
        # Green (0, 255, 0) to Yellow (0, 255, 255)
        color = (0, 255, int(255 * ratio))
        
        # Draw percentage text
        cv2.putText(
            frame, 
            f"Posture: {int(slouch_percentage)}% (Threshold: {self.threshold_percentage}%)", 
            (50, 130), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            color, 
            2
        )
    
    def save_calibration(self):
        """Save calibration data to a file"""
        if not self.calibrated or self.calibration_landmarks is None:
            print("No calibration data to save")
            return False
            
        try:
            # Save calibration data
            with open(self.calibration_file, 'wb') as f:
                pickle.dump(self.calibration_landmarks, f)
                
            print(f"Calibration data saved to {self.calibration_file}")
            return True
        except Exception as e:
            print(f"Error saving calibration data: {e}")
            return False
    
    def load_calibration(self):
        """Load calibration data from a file"""
        if not self.calibration_file:
            print("No calibration file found")
            return False
            
        try:
            with open(self.calibration_file, 'rb') as f:
                self.calibration_landmarks = pickle.load(f)
                
            if self.calibration_landmarks:
                self.calibrated = True
                print(f"Calibration data loaded from {self.calibration_file}")
                return True
            else:
                print("Calibration file exists but contains no data")
                return False
        except Exception as e:
            print(f"Error loading calibration data: {e}")
            return False 