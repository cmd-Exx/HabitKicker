"""PyQt6 GUI for the HabitKicker application"""

import os
import time
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QSlider, QLabel, QCheckBox, QFrame, QSizePolicy,
    QProgressBar, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPixmap, QImage, QIcon, QAction
from camera import Camera
import cv2

class HabitKickerGUI(QMainWindow):
    def __init__(self):

        self.base_dir = os.getcwd()
        self.data_dir = os.path.join(self.base_dir, "data")
        self.sounds_dir = os.path.join(self.base_dir, "sounds")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.sounds_dir, exist_ok=True)

        super().__init__()
        
        # Set window flag to stay on top, hide from taskbar, and remove title bar
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)

        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon(os.path.join(self.data_dir, "HabitKicker.ico"))
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("HabitKicker")
        
        # Create tray menu
        tray_menu = QMenu()
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Handle tray icon clicks
        self.tray_icon.activated.connect(self.tray_icon_clicked)

        # Default settings
        self.default_settings = {
            "nail_distance": 20,
            "hair_distance": 110,
            "nail_detection": True,
            "hair_detection": True,
            "slouch_detection": True,
            "show_notifications": True,
            "show_screen_outline": True,
            "show_red_tint": True,
            "alarm_volume": 15,
            "camera_fps": 2
        }
        
        # Current settings
        self.settings = self.load_settings()
        
        # Initialize camera as None - we'll create it when needed
        self.camera = None
        self.camera_thread = None
        
        # Set up the UI
        self.init_ui()
        
        # Set initial application state
        self.application_running = False
        
        # Camera panel state
        self.panel_expanded = False
        
        # Timer for updating camera feed
        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.update_camera_feed)
        self.camera_timer.start(33)  # Max ~30 fps

        # Automatically start the application
        self.start_application()
        
    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties
        self.setWindowTitle("HabitKicker")
        window_width = 1050
        window_height = 720
        self.setMinimumSize(window_width, window_height)
        screen_geometry = self.screen().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        self.setGeometry(screen_width - window_width + 1, screen_height - window_height + 1, window_width, window_height)
        
        # Create main widget with horizontal layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_horizontal_layout = QHBoxLayout(main_widget)
        main_horizontal_layout.setContentsMargins(0, 0, 0, 0)
        main_horizontal_layout.setSpacing(0)
        
        # Create slide-out panel for camera
        self.panel_widget = QWidget()
        self.panel_widget.setFixedWidth(25)  # Initial collapsed width
        self.panel_widget.setMinimumHeight(window_height)
        panel_layout = QHBoxLayout(self.panel_widget)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        
        # Create the clickable bar
        self.panel_bar = QFrame()
        self.panel_bar.setFixedWidth(25)
        self.panel_bar.setMinimumHeight(window_height)
        self.panel_bar.setStyleSheet("""
            background-color: #333333; 
            border-right: 1px solid #555555;
        """)
        self.panel_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.panel_bar.mousePressEvent = self.toggle_panel
        
        # Add arrow indicator to the panel bar
        self.arrow_label = QLabel("▶")  # Right-pointing arrow
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arrow_label.setStyleSheet("color: #AAAAAA; font-size: 15px;")
        self.arrow_label.setFixedSize(25, 25)
        
        # Create a vertical layout for the panel bar
        panel_bar_layout = QVBoxLayout(self.panel_bar)
        panel_bar_layout.setContentsMargins(0, 0, 0, 0)
        panel_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        panel_bar_layout.addWidget(self.arrow_label)
        
        # Create camera panel content
        self.camera_panel_content = QWidget()
        camera_panel_layout = QVBoxLayout(self.camera_panel_content)
        camera_panel_layout.setContentsMargins(10, 0, 0, 22) # No margin on right border
        camera_panel_layout.setSpacing(16)
        camera_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align contents to top
        
        # Add camera panel header
        camera_header = QLabel("Camera Feed")
        camera_header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        camera_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        camera_header.setStyleSheet("""
            color: #FFFFFF;
            margin-top: 42px;
            margin-bottom: 22px;
        """)
        camera_panel_layout.addWidget(camera_header)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        camera_panel_layout.addWidget(separator)
        
        # Create camera view widget
        self.camera_view = QLabel()
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_view.setFixedSize(635, 413)
        self.camera_view.setStyleSheet("""
            background-color: #222222;
            border: 1px solid #444444;
            border-radius: 4px;
            padding: 2px;
        """)
        self.camera_view.setText("Camera feed will appear here")
        camera_panel_layout.addWidget(self.camera_view)
        
        # Add calibration status section at the bottom of camera panel
        self.calibration_status_frame = QFrame()
        self.calibration_status_frame.setFixedHeight(80)  # Set fixed height
        self.calibration_status_frame.setStyleSheet("""
            background-color: #333333;
            padding: 5px;
        """)
        calibration_status_layout = QVBoxLayout(self.calibration_status_frame)
        calibration_status_layout.setContentsMargins(10, 5, 10, 5)
        calibration_status_layout.setSpacing(5)
        
        # Add calibration message label
        self.calibration_message = QLabel("No calibration in progress")
        self.calibration_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibration_message.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        calibration_status_layout.addWidget(self.calibration_message)
        
        # Add progress bar for calibration
        self.calibration_progress = QProgressBar()
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        self.calibration_progress.setTextVisible(True)
        self.calibration_progress.setFixedHeight(25)
        self.calibration_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #222222;
                text-align: center;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #00AA00;
                border-radius: 2px;
            }
        """)
        calibration_status_layout.addWidget(self.calibration_progress)
        
        # Hide by default
        self.calibration_status_frame.setVisible(False)
        
        # Add to camera panel layout
        camera_panel_layout.addWidget(self.calibration_status_frame)
        
        # Add camera delay slider
        delay_frame = QFrame()
        delay_frame.setStyleSheet("""
            background-color: #333333;
            padding: 5px;
        """)
        delay_frame.setFixedHeight(50)
        delay_layout = QVBoxLayout(delay_frame)
        delay_layout.setContentsMargins(10, 10, 10, 10)
        delay_layout.setSpacing(10)
        
        # Add delay slider controls
        delay_controls = QHBoxLayout()
        delay_label = QLabel("Camera FPS:")
        self.delay_label = delay_label  # Store reference to label
        self.delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_slider.setRange(1, 30)  # 1 to 30 FPS
        initial_fps = self.settings["camera_fps"]
        self.delay_slider.setValue(initial_fps)
        self.delay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.delay_slider.setTickInterval(5)
        self.delay_value_label = QLabel(f"{initial_fps} FPS")
        
        delay_controls.addWidget(delay_label)
        delay_controls.addWidget(self.delay_slider)
        delay_controls.addWidget(self.delay_value_label)
        delay_layout.addLayout(delay_controls)
        
        # Connect delay slider
        self.delay_slider.valueChanged.connect(self.update_delay_value)
        
        # Add to camera panel layout
        camera_panel_layout.addWidget(delay_frame)
        
        # Add stretch at the bottom to push everything up
        camera_panel_layout.addStretch()
        
        # Add widgets to panel layout
        panel_layout.addWidget(self.panel_bar)
        panel_layout.addWidget(self.camera_panel_content)
        panel_layout.addStretch()
        
        # Initially hide camera panel content
        self.camera_panel_content.setVisible(False)
        
        # Add panel to main horizontal layout
        main_horizontal_layout.addWidget(self.panel_widget)
        
        # Create central widget and main layout for controls
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_horizontal_layout.addWidget(central_widget)
        
        # Add title
        title_label = QLabel("HabitKicker")
        title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Add subtitle
        subtitle_label = QLabel("Break bad habits with real-time detection")
        subtitle_label.setFont(QFont("Arial", 12))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle_label)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        # Calibration section
        calibration_frame, calibration_layout = self.create_section_frame("Posture Calibration")
        
        # Calibration button
        self.calibrate_button = QPushButton("Calibrate Posture (Ctrl+C)")
        self.calibrate_button.setMinimumHeight(50)
        self.calibrate_button.clicked.connect(self.calibrate_posture)
        calibration_layout.addWidget(self.calibrate_button)
        
        # Calibration status
        self.calibration_status = QLabel("Status: Not calibrated")
        calibration_layout.addWidget(self.calibration_status)
        
        main_layout.addWidget(calibration_frame)
        
        # Detection settings section
        detection_frame, detection_layout = self.create_section_frame("Detection Settings")
        
        # Nail biting distance slider
        nail_layout = QHBoxLayout()
        nail_label = QLabel("Max Nail Distance:")
        self.nail_slider = QSlider(Qt.Orientation.Horizontal)
        self.nail_slider.setRange(0, 100)
        self.nail_slider.setValue(self.settings["nail_distance"])  # Use saved value
        self.nail_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.nail_slider.setTickInterval(10)
        self.nail_value_label = QLabel(str(self.settings["nail_distance"]))
        
        nail_layout.addWidget(nail_label)
        nail_layout.addWidget(self.nail_slider)
        nail_layout.addWidget(self.nail_value_label)
        detection_layout.addLayout(nail_layout)
        
        # Hair pulling distance slider
        hair_layout = QHBoxLayout()
        hair_label = QLabel("Max Hair Distance:")
        self.hair_slider = QSlider(Qt.Orientation.Horizontal)
        self.hair_slider.setRange(0, 150)
        self.hair_slider.setValue(self.settings["hair_distance"])  # Use saved value
        self.hair_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.hair_slider.setTickInterval(10)
        self.hair_value_label = QLabel(str(self.settings["hair_distance"]))
        
        hair_layout.addWidget(hair_label)
        hair_layout.addWidget(self.hair_slider)
        hair_layout.addWidget(self.hair_value_label)
        detection_layout.addLayout(hair_layout)
        
        # Add detection toggles
        toggle_layout = QHBoxLayout()  # Changed to horizontal layout
        toggle_layout.setSpacing(18)  # Set spacing between toggles
        
        # Nail detection toggle
        nail_toggle_layout = QHBoxLayout()
        nail_toggle_label = QLabel("Nail Biting:")
        self.nail_toggle = QCheckBox()
        self.nail_toggle.setChecked(self.settings["nail_detection"])
        self.nail_toggle.stateChanged.connect(self.toggle_nail_detection)
        nail_toggle_layout.addWidget(nail_toggle_label)
        nail_toggle_layout.addWidget(self.nail_toggle)
        toggle_layout.addLayout(nail_toggle_layout)
        
        # Hair detection toggle
        hair_toggle_layout = QHBoxLayout()
        hair_toggle_label = QLabel("Hair Pulling:")
        self.hair_toggle = QCheckBox()
        self.hair_toggle.setChecked(self.settings["hair_detection"])
        self.hair_toggle.stateChanged.connect(self.toggle_hair_detection)
        hair_toggle_layout.addWidget(hair_toggle_label)
        hair_toggle_layout.addWidget(self.hair_toggle)
        toggle_layout.addLayout(hair_toggle_layout)

        # Slouch detection toggle
        slouch_toggle_layout = QHBoxLayout()
        slouch_toggle_label = QLabel("Slouching:")
        self.slouch_toggle = QCheckBox()
        self.slouch_toggle.setChecked(self.settings["slouch_detection"])
        self.slouch_toggle.stateChanged.connect(self.toggle_slouch_detection)
        slouch_toggle_layout.addWidget(slouch_toggle_label)
        slouch_toggle_layout.addWidget(self.slouch_toggle)
        toggle_layout.addLayout(slouch_toggle_layout)

        # Add stretch at the end to keep toggles left-aligned
        toggle_layout.addStretch()
        
        detection_layout.addLayout(toggle_layout)
        
        # Add restore defaults button
        restore_layout = QHBoxLayout()
        restore_layout.addStretch()
        self.restore_button = QPushButton("Restore Default Settings")
        self.restore_button.clicked.connect(self.restore_default_detection_settings)
        restore_layout.addWidget(self.restore_button)
        detection_layout.addLayout(restore_layout)
        
        # Connect sliders to update functions
        self.nail_slider.valueChanged.connect(self.update_nail_value)
        self.hair_slider.valueChanged.connect(self.update_hair_value)
        
        main_layout.addWidget(detection_frame)
        
        # Alert settings section
        alert_frame, alert_layout = self.create_section_frame("Alert Settings")
        
        # Notification toggle
        notification_layout = QHBoxLayout()
        notification_label = QLabel("Show Notifications (1s):")
        self.notification_checkbox = QCheckBox()
        self.notification_checkbox.setChecked(self.settings["show_notifications"])  # Use saved value
        self.notification_checkbox.stateChanged.connect(self.toggle_notifications)
        
        notification_layout.addWidget(notification_label)
        notification_layout.addStretch()
        notification_layout.addWidget(self.notification_checkbox)
        alert_layout.addLayout(notification_layout)
        
        # Screen outline toggle
        outline_layout = QHBoxLayout()
        outline_label = QLabel("Show Screen Outline (1s):")
        self.outline_checkbox = QCheckBox()
        self.outline_checkbox.setChecked(self.settings["show_screen_outline"])  # Use saved value
        self.outline_checkbox.stateChanged.connect(self.toggle_screen_outline)
        
        outline_layout.addWidget(outline_label)
        outline_layout.addStretch()
        outline_layout.addWidget(self.outline_checkbox)
        alert_layout.addLayout(outline_layout)
        
        # Tint toggle
        tint_layout = QHBoxLayout()
        tint_label = QLabel("Show Tint (3s):")
        self.tint_checkbox = QCheckBox()
        self.tint_checkbox.setChecked(self.settings["show_red_tint"])  # Use saved value
        self.tint_checkbox.stateChanged.connect(self.toggle_tint)
        
        tint_layout.addWidget(tint_label)
        tint_layout.addStretch()
        tint_layout.addWidget(self.tint_checkbox)
        alert_layout.addLayout(tint_layout)
        
        # Volume slider
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Alarm Volume (4s):")
        self.volume_label = volume_label  # Store reference to label
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings["alarm_volume"])  # Use saved value
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setTickInterval(10)
        self.volume_value_label = QLabel(f"{self.settings['alarm_volume']}%")
        
        # Set initial enabled state based on tint setting
        show_tint = self.settings["show_red_tint"]
        self.volume_slider.setEnabled(show_tint)
        self.volume_value_label.setEnabled(show_tint)
        self.volume_label.setEnabled(show_tint)
        
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_value_label)
        alert_layout.addLayout(volume_layout)
        
        # Connect volume slider
        self.volume_slider.valueChanged.connect(self.update_volume_value)
        
        main_layout.addWidget(alert_frame)
        
        # Add spacer at the bottom
        main_layout.addStretch()
        
        # Start/Stop button
        self.start_button = QPushButton("Stop HabitKicker")
        self.start_button.setMinimumHeight(50)
        self.start_button.clicked.connect(self.toggle_application)
        main_layout.addWidget(self.start_button)
        
        # Set up animations
        self.panel_animation = QPropertyAnimation(self.panel_widget, b"minimumWidth")
        self.panel_animation.setDuration(250)
        self.panel_animation.setEasingCurve(QEasingCurve.Type.Linear)

    def toggle_panel(self, event=None):
        """Toggle the camera panel expansion state"""
        if self.panel_expanded:
            # Collapse panel
            self.panel_animation.setStartValue(670)
            self.panel_animation.setEndValue(25)
            self.panel_expanded = False
            self.arrow_label.setText("▶")  # Right-pointing arrow
            # Hide camera panel content
            self.camera_panel_content.setVisible(False)
        else:
            # Expand panel
            self.panel_animation.setStartValue(25)
            self.panel_animation.setEndValue(670)
            self.panel_expanded = True
            self.arrow_label.setText("◀")  # Left-pointing arrow
            # Show camera panel content
            self.camera_panel_content.setVisible(True)
            # Update camera feed immediately when expanded
            self.update_camera_feed()
        
        self.panel_animation.start()
    
    def update_camera_feed(self):
        """Update the camera feed in the panel"""
        # Only update when panel is expanded and camera view is visible
        # or when calibration is in progress
        is_calibrating = hasattr(self, 'camera') and self.camera is not None and self.camera.is_calibrating
        
        if (not self.panel_expanded or not self.camera_panel_content.isVisible()) and not is_calibrating:
            return
            
        if hasattr(self, 'camera') and self.camera is not None and self.camera.cap is not None:
            # Get the current frame from the camera
            frame = self.camera.get_current_frame()
            if frame is not None:
                try:
                    # Convert the OpenCV BGR image to RGB for Qt
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    
                    # Convert to QImage and then to QPixmap
                    qt_image = QImage(rgb_image.data, w, h, w * ch, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)
                    
                    # Scale pixmap to fit the label while maintaining aspect ratio
                    self.camera_view.setPixmap(pixmap.scaled(
                        self.camera_view.width(), 
                        self.camera_view.height(),
                        Qt.AspectRatioMode.KeepAspectRatio
                    ))
                    
                    # Update calibration status if camera is calibrating
                    if is_calibrating:
                        self.update_calibration_status()
                        
                    # If calibrating and panel is not expanded, expand it to show the calibration
                    if is_calibrating and not self.panel_expanded:
                        self.toggle_panel()
                        
                except Exception as e:
                    print(f"Error updating camera feed: {e}")
            else:
                self.camera_view.setText("Camera feed not available")
        else:
            self.camera_view.setText("Camera not initialized")
    
    def update_calibration_status(self):
        """Update the calibration status in the panel"""
        if not hasattr(self, 'camera') or self.camera is None:
            return
            
        # Show the calibration status frame
        self.calibration_status_frame.setVisible(True)
        
        # Get calibration info from the camera/slouch_detector
        if self.camera.is_calibrating:
            # Check if in countdown phase
            if self.camera.slouch_detector.calibration_countdown > 0:
                current_time = time.time()
                elapsed = current_time - self.camera.slouch_detector.calibration_start_time
                remaining = self.camera.slouch_detector.calibration_countdown - elapsed
                
                if remaining > 0:
                    # Update countdown message
                    self.calibration_message.setText(f"Calibration in {int(remaining)+1}...")
                    self.calibration_message.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")
                    self.calibration_progress.setValue(0)
                
            else:
                # In actual calibration phase
                current_time = time.time()
                elapsed = current_time - self.camera.slouch_detector.calibration_start_time
                duration = self.camera.slouch_detector.calibration_duration
                
                if elapsed < duration:
                    # Calculate progress percentage
                    progress = int((elapsed / duration) * 100)
                    
                    # Update UI
                    self.calibration_message.setText("Calibrating posture... Stay still and sit up straight!")
                    self.calibration_message.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")
                    self.calibration_progress.setValue(progress)
        
        # Check if calibration just completed
        elif hasattr(self.camera, 'calibration_complete_time'):
            current_time = time.time()
            if current_time - self.camera.calibration_complete_time < 2:
                # Show completion message
                self.calibration_message.setText("Calibration Complete!")
                self.calibration_message.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")
                self.calibration_progress.setValue(100)
            # Hide the calibration status after the completion message duration
            time.sleep(1)
            self.calibration_status_frame.setVisible(False)
        
        else:
            # No calibration activity, hide the frame
            self.calibration_status_frame.setVisible(False)
    
    def load_settings(self):
        """Load settings from file"""
        settings_path = os.path.join(self.data_dir, "habitkicker_settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    return json.load(f)
            return self.default_settings.copy()
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self.default_settings.copy()
    
    def save_settings(self):
        """Save settings to file"""
        settings_path = os.path.join(self.data_dir, "habitkicker_settings.json")
        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def restore_default_detection_settings(self):
        """Restore detection settings to default values"""
        # Update sliders
        self.nail_slider.setValue(self.default_settings["nail_distance"])
        self.hair_slider.setValue(self.default_settings["hair_distance"])
        
        # Update settings
        self.settings["nail_distance"] = self.default_settings["nail_distance"]
        self.settings["hair_distance"] = self.default_settings["hair_distance"]
        
        # Update detection toggles
        self.nail_toggle.setChecked(True)
        self.hair_toggle.setChecked(True)
        self.slouch_toggle.setChecked(True)
        
        # Update settings for detection toggles
        self.settings["nail_detection"] = True
        self.settings["hair_detection"] = True
        self.settings["slouch_detection"] = True
        
        # Save settings
        self.save_settings()
        
        # Update camera if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.habit_detector.NAIL_PULLING_THRESHOLD = self.default_settings["nail_distance"]
            self.camera.habit_detector.HAIR_PULLING_THRESHOLD = self.default_settings["hair_distance"]
            self.camera.enable_nail_detection = True
            self.camera.enable_hair_detection = True
            self.camera.enable_slouch_detection = True
        
    def create_section_frame(self, title):
        """Create a framed section with title"""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Raised)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Add title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        return frame, layout
        
    def update_nail_value(self, value):
        """Update the nail biting distance value label"""
        self.nail_value_label.setText(str(value))
        # Update settings
        self.settings["nail_distance"] = value
        self.save_settings()
        # Update camera if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.habit_detector.NAIL_PULLING_THRESHOLD = value
        
    def update_hair_value(self, value):
        """Update the hair pulling distance value label"""
        self.hair_value_label.setText(str(value))
        # Update settings
        self.settings["hair_distance"] = value
        self.save_settings()
        # Update camera if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.habit_detector.HAIR_PULLING_THRESHOLD= value
        
    def update_volume_value(self, value):
        """Update the volume value label"""
        self.volume_value_label.setText(f"{value}%")
        # Update settings
        self.settings["alarm_volume"] = value
        self.save_settings()

        # Update volume in screen outline if available
        if hasattr(self, 'camera') and self.camera and hasattr(self.camera, 'screen_overlay'):
            # Convert percentage to a value between 0 and 1
            volume = value / 100.0
            self.camera.screen_overlay.alarm_volume = volume
            # Update the sound volume if it exists
            if hasattr(self.camera.screen_overlay, 'alarm_sound') and self.camera.screen_overlay.alarm_sound:
                self.camera.screen_overlay.alarm_sound.set_volume(volume)
                self.camera.screen_overlay.audio_initialized = True
    
    def update_delay_value(self, value):
        """Update the camera processing delay value label"""
        self.delay_value_label.setText(f"{value} FPS")
        # Update settings
        self.settings["camera_fps"] = value
        self.save_settings()
        # Update camera delay if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.processing_delay = 1.0 / value  # Convert FPS directly to seconds
    
    def toggle_notifications(self, state):
        """Toggle notifications on/off"""
        show_notifications = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings["show_notifications"] = show_notifications
        self.save_settings()
        
        # Update notification settings in camera if applicable
        if hasattr(self, 'camera') and self.camera is not None:
            if hasattr(self.camera.screen_overlay, 'notification_visible'):
                self.camera.screen_overlay.show_notification = show_notifications
                # If notifications are disabled and a notification is currently visible, hide it
                if not show_notifications and self.camera.screen_overlay.notification_window and self.camera.screen_overlay.notification_window.winfo_exists():
                    self.camera.screen_overlay.notification_window.withdraw()
            print(f"Notifications {'enabled' if show_notifications else 'disabled'}")
        
    def toggle_screen_outline(self, state):
        """Toggle screen outline on/off"""
        show_outline = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings["show_screen_outline"] = show_outline
        self.save_settings()
        
        # Update screen outline settings
        if hasattr(self, 'camera') and self.camera is not None:
            # Set the property that controls whether outlines should be shown
            self.camera.screen_overlay.show_outline_enabled = show_outline
            # Update the outline transparency instead of hiding it
            if not show_outline:
                self.camera.screen_overlay.set_outline_transparency(0)
            else:
                self.camera.screen_overlay.set_outline_transparency(1)
            print(f"Screen outline {'enabled' if show_outline else 'disabled'}")

    def toggle_tint(self, state):
        """Toggle tint on/off"""
        show_tint = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings["show_red_tint"] = show_tint
        self.save_settings()
        
        # Enable/disable volume controls based on tint state
        self.volume_slider.setEnabled(show_tint)
        self.volume_value_label.setEnabled(show_tint)
        self.volume_label.setEnabled(show_tint)
        
        # Update tint settings
        if hasattr(self, 'camera') and self.camera is not None:
            # Add a show_tint property to the screen_overlay object
            self.camera.screen_overlay.show_red_tint = show_tint
            # If tint is currently showing and should be disabled, hide it
            if not show_tint and self.camera.screen_overlay.is_tinted:
                self.camera.screen_overlay.hide_tint()
            # If tint should be enabled and we're already in red outline state, show it
            elif show_tint and self.camera.screen_overlay.current_color == "red":
                self.camera.screen_overlay.show_tint()
            print(f"Tint {'enabled' if show_tint else 'disabled'}")
    
    def toggle_camera_window(self):
        """Toggle the camera window visibility"""
        self.toggle_panel()
        
    def calibrate_posture(self):
        """Calibrate posture using the camera"""
        if hasattr(self, 'camera') and self.camera is not None:
            try:
                # Temporarily enable slouch detection
                self.temp_enable_slouch_detection = self.camera.enable_slouch_detection
                self.camera.enable_slouch_detection = True

                # Open the slide-out panel if it's not already open
                self.temp_panel_expanded = self.panel_expanded
                if not self.panel_expanded:
                    self.toggle_panel()
                
                # Show calibration status panel
                self.calibration_status_frame.setVisible(True)
                self.calibration_message.setText("Preparing for calibration...")
                self.calibration_progress.setValue(0)
                
                # Store current processing delay and set to 0 for calibration
                self.camera.stored_processing_delay = self.camera.processing_delay
                self.camera.processing_delay = 0
                
                self.camera.start_calibration()
                self.calibration_status.setText("Status: Calibrating...")
                
                # Check calibration status periodically
                self.calibration_timer = QTimer()
                self.calibration_timer.timeout.connect(self.check_calibration_status)
                self.calibration_timer.start(1000)  # Check every second

            except Exception as e:
                print(f"Error starting calibration: {e}")
                self.calibration_status.setText("Status: Calibration failed")
                # Restore processing delay if there's an error
                if hasattr(self.camera, 'stored_processing_delay'):
                    self.camera.processing_delay = self.camera.stored_processing_delay
        else:
            print("Camera not initialized. Start the application first.")
            self.calibration_status.setText("Status: Camera not initialized")
            
    def check_calibration_status(self):
        """Check if calibration is complete"""
        if hasattr(self, 'camera') and self.camera is not None:
            # Check if the slouch detector is calibrated or if calibration just completed
            is_calibrated = self.camera.slouch_detector.calibrated
            just_completed = hasattr(self.camera, 'calibration_complete_time') and \
                            time.time() - self.camera.calibration_complete_time < 2
                            
            if is_calibrated:
                self.calibration_status.setText("Status: Calibrated")
                
                # Restore the original processing delay if calibration is complete
                if hasattr(self.camera, 'stored_processing_delay'):
                    self.camera.processing_delay = self.camera.stored_processing_delay
                    delattr(self.camera, 'stored_processing_delay')
                
                # If calibration just completed, make sure we update the panel UI
                if just_completed:
                    self.update_calibration_status()
                
                # Close the slide-out panel after calibration is complete
                if self.panel_expanded and not self.temp_panel_expanded:
                    QTimer.singleShot(1000, self.toggle_panel)
                
                # Restore enable slouch detection value
                self.camera.enable_slouch_detection = self.temp_enable_slouch_detection

                # Stop the timer if we were using one
                if hasattr(self, 'calibration_timer') and self.calibration_timer.isActive():
                    self.calibration_timer.stop()
            else:
                # Update the calibration status message and progress
                self.update_calibration_status()
                
                # If no longer calibrating but not calibrated, something went wrong
                if not self.camera.is_calibrating:
                    self.calibration_status.setText("Status: Not calibrated")
                    # Restore the processing delay if calibration failed
                    if hasattr(self.camera, 'stored_processing_delay'):
                        self.camera.processing_delay = self.camera.stored_processing_delay
                        delattr(self.camera, 'stored_processing_delay')
                    if hasattr(self, 'calibration_timer') and self.calibration_timer.isActive():
                        self.calibration_timer.stop()
        else:
            self.calibration_status.setText("Status: Camera not initialized")
            # Stop timer if active
            if hasattr(self, 'calibration_timer') and self.calibration_timer.isActive():
                self.calibration_timer.stop()
            
    def toggle_application(self):
        """Toggle the application between running and stopped states"""
        if self.application_running:
            self.stop_application()
            if self.panel_expanded:
                self.toggle_panel()
        else:
            self.start_application()
            
    def start_application(self):
        """Start the HabitKicker application"""
        try:
            # Update UI
            self.start_button.setText("Stop HabitKicker")
            self.application_running = True
            
            # Initialize camera with current settings
            if not hasattr(self, 'camera') or self.camera is None:
                nail_distance = self.settings["nail_distance"]
                hair_distance = self.settings["hair_distance"]
                
                self.camera = Camera(
                    max_nail_pulling_distance = nail_distance,
                    max_hair_pulling_distance = hair_distance,
                    slouch_threshold = 15,
                    gui_window = self
                )
                
                # Set camera processing delay
                self.camera.processing_delay = 1.0 / self.settings["camera_fps"] # Convert FPS to seconds
                
                # Set alarm volume
                volume = self.settings["alarm_volume"] / 100.0  # Convert percentage to 0-1 range
                self.camera.screen_overlay.alarm_volume = volume
                
                # Wait until tkinter windows are initialized
                while not self.camera.screen_overlay.root or not self.camera.screen_overlay.windows:
                    time.sleep(0.1)

                # Enable all settings
                self.notification_checkbox.setEnabled(True)
                self.outline_checkbox.setEnabled(True)
                self.tint_checkbox.setEnabled(True)
                if self.settings["show_red_tint"]:
                    self.volume_slider.setEnabled(True)
                    self.volume_value_label.setEnabled(True)
                    self.volume_label.setEnabled(True)
                else:
                    self.volume_slider.setEnabled(False)
                    self.volume_value_label.setEnabled(False)
                    self.volume_label.setEnabled(False)

                self.nail_toggle.setEnabled(True)
                self.hair_toggle.setEnabled(True)
                self.slouch_toggle.setEnabled(True)
                self.nail_slider.setEnabled(True)
                self.nail_value_label.setEnabled(True)
                self.hair_slider.setEnabled(True)
                self.hair_value_label.setEnabled(True)
                self.calibrate_button.setEnabled(True)
                self.restore_button.setEnabled(True)

                # Restore settings
                self.toggle_notifications(self.settings["show_notifications"] * 2)
                self.toggle_screen_outline(self.settings["show_screen_outline"] * 2)
                self.toggle_tint(self.settings["show_red_tint"] * 2)

                # Start camera processing
                self.camera.start_camera_no_window()
                
                # Wait until camera is fully initialized
                while not self.camera.cap:
                    time.sleep(0.1)
                # Additional delay to ensure full initialization of alert windows
                time.sleep(-self.settings["camera_fps"]/30 + 1)

                # Configure detection settings
                self.camera.enable_nail_detection = self.settings["nail_detection"]
                self.camera.enable_hair_detection = self.settings["hair_detection"]
                self.camera.enable_slouch_detection = self.settings["slouch_detection"]

                self.camera.screen_overlay.notification_visible = self.settings["show_notifications"]
                self.camera.screen_overlay.show_outline_enabled = self.settings["show_screen_outline"]
                self.camera.screen_overlay.show_red_tint = self.settings["show_red_tint"]

                # Check calibration status
                self.temp_enable_slouch_detection = self.camera.enable_slouch_detection
                self.check_calibration_status()

                # Open panel on startup
                self.toggle_panel()

                # Automatically select window
                self.focus_window()

                print("HabitKicker initialized successfully")
            else:
                print("HabitKicker is already running")
                
        except Exception as e:
            print(f"Error starting HabitKicker: {e}")
            self.start_button.setText("Start HabitKicker")
            self.application_running = False
            
    def stop_application(self):
        """Stop the HabitKicker application"""
        try:
            # Update UI
            self.start_button.setText("Start HabitKicker")
            self.calibration_status.setText("Status: Camera not initialized")
            self.application_running = False

            # Disable alerts
            if hasattr(self, 'camera') and self.camera is not None:
                if hasattr(self.camera.screen_overlay, 'notification_visible'):
                    self.camera.screen_overlay.show_notification = False
                    if self.camera.screen_overlay.notification_window and self.camera.screen_overlay.notification_window.winfo_exists():
                        self.camera.screen_overlay.notification_window.withdraw()

                self.camera.screen_overlay.show_outline_enabled = False
                self.camera.screen_overlay.set_outline_transparency(0)

                self.camera.screen_overlay.show_red_tint = False
                if self.camera.screen_overlay.is_tinted:
                    self.camera.screen_overlay.hide_tint()

            # Disable all settings
            self.notification_checkbox.setEnabled(False)
            self.outline_checkbox.setEnabled(False)
            self.tint_checkbox.setEnabled(False)
            self.volume_slider.setEnabled(False)
            self.volume_value_label.setEnabled(False)
            self.volume_label.setEnabled(False)

            self.nail_toggle.setEnabled(False)
            self.hair_toggle.setEnabled(False)
            self.slouch_toggle.setEnabled(False)
            self.nail_slider.setEnabled(False)
            self.nail_value_label.setEnabled(False)
            self.hair_slider.setEnabled(False)
            self.hair_value_label.setEnabled(False)
            self.calibrate_button.setEnabled(False)
            self.restore_button.setEnabled(False)

            # Stop camera and cleanup
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.stop_camera()
                self.camera = None
                
            print("HabitKicker stopped successfully")
            
        except Exception as e:
            print(f"Error stopping HabitKicker: {e}")
            
    def closeEvent(self, event):
        """Override close event to minimize to tray instead of closing"""
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.quit_application()
            event.accept()

    def resizeWindow(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        # Update camera feed when window is resized
        self.update_camera_feed()

    def toggle_nail_detection(self, state):
        """Toggle nail detection on/off"""
        enabled = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings["nail_detection"] = enabled
        self.save_settings()
        # Update camera if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.enable_nail_detection = enabled
        print(f"Nail detection {'enabled' if enabled else 'disabled'}")
        
    def toggle_hair_detection(self, state):
        """Toggle hair detection on/off"""
        enabled = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings["hair_detection"] = enabled
        self.save_settings()
        # Update camera if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.enable_hair_detection = enabled
        print(f"Hair detection {'enabled' if enabled else 'disabled'}")
        
    def toggle_slouch_detection(self, state):
        """Toggle slouch detection on/off"""
        enabled = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings["slouch_detection"] = enabled
        self.save_settings()
        # Update camera if running
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.enable_slouch_detection = enabled
        print(f"Slouch detection {'enabled' if enabled else 'disabled'}")

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Check if Ctrl+C is pressed
        if event.modifiers() and Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C:
            self.calibrate_posture()
        elif event.modifiers() and Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_T:
            self.toggle_panel()
        elif event.modifiers() and Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_X:
            self.hide()
        else:
            # Pass other key events to parent class
            super().keyPressEvent(event)

    def quit_application(self):
        """Quit the application"""
        if self.application_running:
            self.stop_application()
        QApplication.quit()

    def tray_icon_clicked(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.focus_window()

    def focus_window(self):
        """Ensure the main window stays on top."""
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        QTimer.singleShot(0, lambda: (self.activateWindow(), self.raise_(), self.setFocus()))
        self.show()
        self.raise_()
        self.activateWindow()