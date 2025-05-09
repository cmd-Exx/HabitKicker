"""Configuration class for MediaPipe landmark indices"""

class LandmarkConfig:
    # Mouth landmarks
    MOUTH_LANDMARKS = [13, 14]  # Lip center points
    
    # Forehead landmarks
    FOREHEAD_LANDMARKS = [
        93, 234, 127, 162, 21, 54, 103,  # Left side
        # 67, 109, 10, 338, 297,  # Center (excluded)
        332, 284, 251, 389, 356, 454, 323  # Right side
    ]  # Head circumference points
    
    # Hand landmarks
    FINGERTIP_LANDMARKS = [4, 8, 12, 16, 20]  # Fingertips
    THUMB_TIP = 4  # Thumb tip
    OTHER_FINGERTIPS = [8, 12, 16, 20]  # Other fingertips 