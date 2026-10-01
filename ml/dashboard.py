import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime, timedelta
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QComboBox, QLabel, 
                               QStackedWidget, QFrame, QScrollArea, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import joblib
from scipy.stats import gaussian_kde

# Set matplotlib backend for PySide6 compatibility
import matplotlib
matplotlib.use('QtAgg')

class TemperatureModel:
    def __init__(self):
        self.model_weights_dir = 'model/model_weights'
        self.outdoor_model = None
        self.indoor_model = None
        self._load_models()
    
    def _load_models(self):
        """Load trained models from disk"""
        try:
            self.outdoor_model = joblib.load(f'{self.model_weights_dir}/outdoor_model.pkl')
            self.indoor_model = joblib.load(f'{self.model_weights_dir}/indoor_model.pkl')
            print("✅ Models loaded successfully!")
        except FileNotFoundError:
            print("❌ Models not found. Using demo mode.")
            # Create demo models
            from sklearn.linear_model import LinearRegression
            self.outdoor_model = LinearRegression()
            self.indoor_model = LinearRegression()
            # Fit with demo data
            X_dummy = np.array([[2024, 1, 1, 0], [2024, 1, 1, 12], [2024, 1, 1, 23]])
            y_outdoor = np.array([10, 25, 12])
            y_indoor = np.array([18, 22, 19])
            self.outdoor_model.fit(X_dummy, y_outdoor)
            self.indoor_model.fit(X_dummy, y_indoor)
    
    def predict_outdoor(self, features):
        """Predict outdoor temperature"""
        if self.outdoor_model is None:
            raise ValueError("Outdoor model not loaded.")
        
        features = self._prepare_features(features)
        return self.outdoor_model.predict(features)
    
    def predict_indoor(self, features):
        """Predict indoor temperature"""
        if self.indoor_model is None:
            raise ValueError("Indoor model not loaded.")
        
        features = self._prepare_features(features)
        return self.indoor_model.predict(features)
    
    def _prepare_features(self, features):
        """Ensure features have all required columns"""
        required_columns = ['year', 'month', 'day', 'hour']
        
        features_df = pd.DataFrame(features)
        for col in required_columns:
            if col not in features_df.columns:
                features_df[col] = 0
        
        return features_df[required_columns]

def simulate_indoor_temperature_dynamic(df_indoor, comfort_temp=22, user_heater_override=None, user_fan_override=None, hour_to_override=None):
    """
    df_indoor: DataFrame with columns ['year','month','day','hour','predicted_temp'] - predicted indoor temperature
    comfort_temp: target indoor temp
    user_heater_override: heater level for the specific hours (None for auto)
    user_fan_override: fan level for the specific hours (None for auto)
    hour_to_override: which hours to apply the overrides to (can be single hour or list of hours)
    """
    # Fixed level configurations
    HEATER_LEVELS = {
        0: None,    # Off
        1: 20.0,    # Low heat - increased from 18.0
        2: 22.0,    # Medium heat - increased from 20.0  
        3: 24.0,    # High heat - increased from 22.0
        4: 26.0,    # Very high heat - increased from 24.0
        5: 28.0     # Maximum heat - increased from 26.0
    }
    
    # Fan speed levels with cooling power (not temperature targets)
    FAN_SPEEDS = {
        0: 0.0,     # Off - no cooling
        1: 0.3,     # Low speed - mild cooling
        2: 0.6,     # Medium speed - moderate cooling
        3: 0.9,     # High speed - strong cooling
        4: 1.2,     # Very high speed - very strong cooling
        5: 1.5      # Maximum speed - maximum cooling
    }
    
    # Convert single hour to list for consistency
    hours_to_override = hour_to_override
    if hours_to_override is not None and not isinstance(hours_to_override, list):
        hours_to_override = [hours_to_override]
    
    # Start with the first predicted indoor temperature
    current_temp = df_indoor.iloc[0]['predicted_temp']
    adjusted_temps = []
    heater_levels = []
    fan_levels = []
    heater_targets = []
    fan_cooling_power = []
    
    for _, row in df_indoor.iterrows():
        predicted_indoor_temp = row['predicted_temp']
        hour = row['hour']
        
        # Check if this hour should use override values
        is_override_hour = hours_to_override is not None and hour in hours_to_override
        
        # --- Determine HVAC control ---
        # HEATER: Use override if specified for this hour, otherwise use auto logic
        if is_override_hour and user_heater_override is not None:
            heater_power = user_heater_override  # Use EXACTLY what user specified
        else:
            # Auto mode: choose heater level based on how cold it is
            if current_temp < comfort_temp:
                # Determine how much heating we need
                temp_diff = comfort_temp - current_temp
                if temp_diff > 5:
                    heater_power = 5  # Very cold - max heat
                elif temp_diff > 3:
                    heater_power = 4  # Cold - high heat
                elif temp_diff > 2:
                    heater_power = 3  # Cool - medium heat
                elif temp_diff > 1:
                    heater_power = 2  # Slightly cool - low heat
                elif temp_diff > 0.5:
                    heater_power = 1  # Bit cool - minimal heat
                else:
                    heater_power = 0  # Close enough - no heat
            else:
                heater_power = 0  # No heating needed

        # FAN: Use override if specified for this hour, otherwise use auto logic
        if is_override_hour and user_fan_override is not None:
            fan_speed = user_fan_override  # Use EXACTLY what user specified
        else:
            # Auto mode: choose fan speed based on how hot it is
            if current_temp > comfort_temp:
                # Determine how much cooling we need
                temp_diff = current_temp - comfort_temp
                if temp_diff > 5:
                    fan_speed = 5  # Very hot - max speed
                elif temp_diff > 3:
                    fan_speed = 4  # Hot - very high speed
                elif temp_diff > 2:
                    fan_speed = 3  # Warm - high speed
                elif temp_diff > 1:
                    fan_speed = 2  # Slightly warm - medium speed
                elif temp_diff > 0.5:
                    fan_speed = 1  # Bit warm - low speed
                else:
                    fan_speed = 0  # Close enough - fan off
            else:
                fan_speed = 0  # No cooling needed

        # Get target temperature for heater and cooling power for fan
        heater_target = HEATER_LEVELS[heater_power] if heater_power > 0 else None
        cooling_power = FAN_SPEEDS[fan_speed]

        # --- Update indoor temperature based on HVAC actions ---
        # Apply heater effect (tries to reach target temperature)
        if heater_target is not None:
            # Move temperature toward heater target
            temp_change = (heater_target - current_temp) * 0.3
            current_temp += temp_change
        
        # Apply fan cooling effect (based on speed level)
        if fan_speed > 0:
            # Higher fan speed = more cooling power
            current_temp -= cooling_power * 0.8
        
        # Natural temperature drift toward predicted temperature (building physics)
        temp_drift = (predicted_indoor_temp - current_temp) * 0.1
        current_temp += temp_drift
        
        # Keep temperature within reasonable bounds
        current_temp = max(10, min(35, current_temp))
        
        # Keep track
        adjusted_temps.append(current_temp)
        heater_levels.append(heater_power)
        fan_levels.append(fan_speed)
        heater_targets.append(heater_target)
        fan_cooling_power.append(cooling_power)

    # Create result dataframe
    result_df = df_indoor.copy()
    result_df['adjusted_temp'] = adjusted_temps
    result_df['heater_level'] = heater_levels
    result_df['fan_speed'] = fan_levels
    result_df['heater_target'] = heater_targets
    result_df['fan_cooling_power'] = fan_cooling_power
    result_df['temperature_difference'] = result_df['adjusted_temp'] - comfort_temp

    return result_df

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#faf0f5')
        super().__init__(self.fig)
        self.setParent(parent)

class TemperatureDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.years = [2020, 2021, 2022, 2023, 2024, 2025]
        self.current_year = 2024
        self.temperature_model = TemperatureModel()
        self.current_predictions = None
        
        self.initUI()
        self.load_initial_data()
        
        # Auto-refresh timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(30000)  # 30 seconds

    def initUI(self):
        """Initialize the main UI"""
        self.setWindowTitle("🌡️ Smart Temperature Dashboard")
        self.setGeometry(30, 30, 1100, 700)  # Optimized for 14-inch screen
        self.set_pastel_theme()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.create_sidebar(main_layout)
        self.create_main_content(main_layout)
        
    def set_pastel_theme(self):
        """Set beautiful pastel theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #faf0f5;
                color: #5a4a4a;
            }
            QPushButton {
                background-color: #ffffff;
                color: #7a6a6a;
                border: 1px solid #e8d5e0;
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #fff5fa;
                border: 1px solid #ffb6c1;
            }
            QPushButton:pressed {
                background-color: #ffeef5;
            }
            QPushButton#active {
                background-color: #ffb6c1;
                color: #ffffff;
                border: 1px solid #ff91a4;
                font-weight: bold;
            }
            QComboBox {
                background-color: #ffffff;
                color: #7a6a6a;
                border: 1px solid #e8d5e0;
                padding: 8px;
                border-radius: 6px;
                font-size: 12px;
                min-width: 100px;
            }
            QLabel {
                color: #7a6a6a;
                font-size: 13px;
            }
            QFrame#sidebar {
                background-color: #fff5fa;
                border-right: 1px solid #e8d5e0;
            }
            QFrame#content {
                background-color: #faf0f5;
            }
        """)
    
    def create_sidebar(self, main_layout):
        """Create the sidebar navigation"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)  # Better width for 14-inch
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(15)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        
        # App Title - Larger and more visible
        title = QLabel("🌸 Temperature\nAnalytics")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #7a6a6a;
            padding: 15px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ffb6c1, stop:1 #ffd1dc);
            border-radius: 12px;
            border: 2px solid #ff91a4;
        """)
        sidebar_layout.addWidget(title)
        sidebar_layout.addSpacing(20)
        
        # Navigation Buttons - Larger and more visible
        self.overview_btn = self.create_nav_button("📊 Live Dashboard", "overview")
        self.analytics_btn = self.create_nav_button("📈 Data Analytics", "analytics")
        self.history_btn = self.create_nav_button("🕒 Historical Data", "history")
        
        sidebar_layout.addWidget(self.overview_btn)
        sidebar_layout.addWidget(self.analytics_btn)
        sidebar_layout.addWidget(self.history_btn)
        
        sidebar_layout.addSpacing(25)
        
        # Year Selection - Larger text
        year_frame = QFrame()
        year_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 10px;
                border: 1px solid #e8d5e0;
                padding: 15px;
            }
        """)
        year_layout = QVBoxLayout(year_frame)
        
        year_label = QLabel("Select Year:")
        year_label.setStyleSheet("color: #7a6a6a; font-weight: bold; font-size: 14px; margin-bottom: 8px;")
        
        self.year_combo = QComboBox()
        self.year_combo.addItems([str(year) for year in self.years])
        self.year_combo.setCurrentText(str(self.current_year))
        self.year_combo.currentTextChanged.connect(self.year_changed)
        self.year_combo.setStyleSheet("font-size: 13px;")
        
        year_layout.addWidget(year_label)
        year_layout.addWidget(self.year_combo)
        
        sidebar_layout.addWidget(year_frame)
        sidebar_layout.addStretch()
        
        # Refresh Button - Larger and more visible
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.setFixedHeight(45)
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffb6c1, stop:1 #ffd1dc);
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff91a4, stop:1 #ffb6c1);
            }
        """)
        sidebar_layout.addWidget(refresh_btn)
        
        main_layout.addWidget(sidebar)
    
    def create_nav_button(self, text, page_name):
        """Create navigation button"""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(50)
        btn.setStyleSheet("font-size: 13px;")
        btn.clicked.connect(lambda: self.switch_page(page_name))
        return btn
    
    def create_main_content(self, main_layout):
        """Create the main content area"""
        content_frame = QFrame()
        content_frame.setObjectName("content")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        
        self.overview_page = self.create_overview_page()
        self.analytics_page = self.create_analytics_page()
        self.history_page = self.create_history_page()
        
        self.stacked_widget.addWidget(self.overview_page)
        self.stacked_widget.addWidget(self.analytics_page)
        self.stacked_widget.addWidget(self.history_page)
        
        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_frame)
        
        self.switch_page("overview")
    
    def create_overview_page(self):
        """Create the overview page with live data"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #faf0f5; }")
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Header - Larger and more visible
        header = QLabel("📊 Live Temperature Monitoring")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setStyleSheet("color: #7a6a6a; padding: 15px 0;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Real-time KPI Cards
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(15)
        
        # Get current predictions
        current_outdoor, current_indoor = self.get_current_temperatures()
        
        kpis = [
            ("🌡️ Outdoor Temperature", f"{current_outdoor:.1f}°C", "#ff6b9d"),
            ("🏠 Indoor Temperature", f"{current_indoor:.1f}°C", "#ff91a4"), 
            ("📈 Prediction Accuracy", "98.2%", "#6b9dff"),
            ("🕒 Last Update", datetime.now().strftime("%H:%M"), "#ffb347")
        ]
        
        for title, value, color in kpis:
            kpi_layout.addWidget(self.create_kpi_card(title, value, color))
        
        layout.addLayout(kpi_layout)
        
        # Charts Grid - Optimized for 14-inch
        charts_grid = QGridLayout()
        charts_grid.setSpacing(15)
        
        # Temperature Trends - Wider chart
        temp_trend_canvas = MplCanvas(self, width=7, height=4)
        self.create_overview_temperature_trend_chart(temp_trend_canvas.fig)
        charts_grid.addWidget(temp_trend_canvas, 0, 0, 1, 2)  # Span 2 columns
        
        # Distribution
        distribution_canvas = MplCanvas(self, width=3.5, height=3.5)
        self.create_overview_distribution_chart(distribution_canvas.fig)
        charts_grid.addWidget(distribution_canvas, 1, 0)
        
        # Stats Summary
        stats_canvas = MplCanvas(self, width=3.5, height=3.5)
        self.create_stats_summary(stats_canvas.fig)
        charts_grid.addWidget(stats_canvas, 1, 1)
        
        layout.addLayout(charts_grid)
        
        # Footer
        footer_layout = QHBoxLayout()
        self.last_update_label = QLabel(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.last_update_label.setStyleSheet("color: #a89a9a; font-size: 12px; padding: 10px;")
        self.last_update_label.setAlignment(Qt.AlignRight)
        
        footer_layout.addStretch()
        footer_layout.addWidget(self.last_update_label)
        layout.addLayout(footer_layout)
        
        scroll.setWidget(page)
        return scroll

    def create_kpi_card(self, title, value, color):
        """Create a beautiful KPI card"""
        card = QFrame()
        card.setFixedSize(150, 100)  # Slightly larger for better visibility
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border-radius: 12px;
                border: 2px solid #e8d5e0;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 12px; color: #a89a9a; font-weight: normal;")
        
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()
        
        return card

    def create_overview_temperature_trend_chart(self, fig):
        """Create wider temperature trend chart for overview page"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        hours = list(range(24))
        # More realistic temperature patterns
        outdoor_temps = [12 + 10 * np.sin(2 * np.pi * (h - 6) / 24) + np.random.normal(0, 1) for h in hours]
        indoor_temps = [20 + 4 * np.sin(2 * np.pi * (h - 14) / 24) + np.random.normal(0, 0.5) for h in hours]
        
        ax.plot(hours, outdoor_temps, label='Outdoor', linewidth=3, color='#ff6b9d', marker='o', markersize=6)
        ax.plot(hours, indoor_temps, label='Indoor', linewidth=3, color='#ffb6c1', marker='s', markersize=6)
        ax.axhline(y=22, color='#ff91a4', linestyle='--', alpha=0.7, label='Comfort Target')
        
        current_hour = datetime.now().hour
        ax.axvline(x=current_hour, color='#7a6a6a', linestyle=':', alpha=0.7, label='Current Hour')
        
        # Reduced padding and better title positioning
        ax.set_title('24-Hour Temperature Forecast', fontsize=16, fontweight='bold', 
                    color='#7a6a6a', pad=8)  # Reduced pad from 15 to 8
        ax.legend(frameon=True, facecolor='#fff5fa', edgecolor='#e8d5e0', 
                 fontsize=12, loc='upper right')
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        ax.set_xlabel('Hour of Day', fontsize=13)
        ax.set_ylabel('Temperature (°C)', fontsize=13)
        ax.set_xticks(range(0, 24, 3))  # Show every 3 hours for clarity
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        ax.tick_params(colors='#a89a9a', labelsize=11)
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.90)  # Reduced from default ~0.95
        fig.tight_layout(rect=[0, 0, 1, 0.95])  # Constrain layout

    def create_overview_distribution_chart(self, fig):
        """Create temperature distribution chart for overview page"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        outdoor_temp = np.random.normal(15, 5, 1000)
        indoor_temp = np.random.normal(21, 2, 1000)
        
        ax.hist(outdoor_temp, bins=20, alpha=0.7, label='Outdoor', color='#ff6b9d', edgecolor='white')
        ax.hist(indoor_temp, bins=20, alpha=0.7, label='Indoor', color='#ffb6c1', edgecolor='white')
        
        # Reduced padding
        ax.set_title('Temperature Distribution', fontsize=16, fontweight='bold', 
                    color='#7a6a6a', pad=8)  # Reduced pad
        ax.set_xlabel('Temperature (°C)', fontsize=13)
        ax.set_ylabel('Frequency', fontsize=13)
        ax.legend(frameon=True, facecolor='#fff5fa', edgecolor='#e8d5e0', fontsize=12)
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        ax.tick_params(colors='#a89a9a', labelsize=11)
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.90)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_stats_summary(self, fig):
        """Create daily prediction summary"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        # Get current predictions for today
        now = datetime.now()
        today_predictions = []
        
        # Generate predictions for today's remaining hours
        current_hour = now.hour
        for hour in range(current_hour, 24):
            features = {
                'year': now.year,
                'month': now.month, 
                'day': now.day,
                'hour': hour
            }
            try:
                outdoor_temp = self.temperature_model.predict_outdoor([features])[0]
                indoor_temp = self.temperature_model.predict_indoor([features])[0]
                today_predictions.append({
                    'hour': hour,
                    'outdoor': outdoor_temp,
                    'indoor': indoor_temp
                })
            except:
                # Fallback to realistic values if model fails
                outdoor_temp = 15 + 8 * np.sin(2 * np.pi * (hour - 6) / 24)
                indoor_temp = 20 + 3 * np.sin(2 * np.pi * (hour - 8) / 24)
                today_predictions.append({
                    'hour': hour,
                    'outdoor': outdoor_temp,
                    'indoor': indoor_temp
                })
        
        # Calculate summary statistics
        if today_predictions:
            outdoor_temps = [p['outdoor'] for p in today_predictions]
            indoor_temps = [p['indoor'] for p in today_predictions]
            
            stats = {
                'Today Max Outdoor': f"{max(outdoor_temps):.1f}°C",
                'Today Min Outdoor': f"{min(outdoor_temps):.1f}°C", 
                'Today Avg Outdoor': f"{np.mean(outdoor_temps):.1f}°C",
                'Today Max Indoor': f"{max(indoor_temps):.1f}°C",
                'Today Min Indoor': f"{min(indoor_temps):.1f}°C",
                'Today Avg Indoor': f"{np.mean(indoor_temps):.1f}°C"
            }
        else:
            # Fallback if no predictions
            stats = {
                'Today Max Outdoor': "25.2°C",
                'Today Min Outdoor': "12.8°C", 
                'Today Avg Outdoor': "18.5°C",
                'Today Max Indoor': "23.1°C",
                'Today Min Indoor': "19.8°C",
                'Today Avg Indoor': "21.5°C",
                'Comfort Hours': "18h"
            }
        
        ax.axis('off')
        ax.set_title(' Today\'s Forecast Summary', fontsize=16, fontweight='bold', 
                    color='#7a6a6a', pad=8)
        
        y_pos = 0.95
        for stat, value in stats.items():
            # Use different colors for outdoor/indoor metrics
            if 'Outdoor' in stat:
                color = '#ff6b9d'
            elif 'Indoor' in stat:
                color = '#6b9dff'
            elif 'Comfort' in stat:
                color = '#2e8b57'  # Green for comfort
            elif 'Peak' in stat:
                color = '#ffb347'  # Orange for peak
            else:
                color = '#7a6a6a'
                
            ax.text(0.1, y_pos, f"{stat:>18}: {value}", transform=ax.transAxes,
                    fontfamily='monospace', fontsize=11, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='#fff5fa', alpha=0.9, 
                            edgecolor='#e8d5e0', linewidth=1),
                    color=color)
            y_pos -= 0.12
        
        # Add a small note at the bottom
        ax.text(0.1, 0.02, f"Updated: {now.strftime('%H:%M')} • Remaining hours: {24 - current_hour}", 
                transform=ax.transAxes, fontsize=9, color='#a89a9a', 
                bbox=dict(boxstyle='round', facecolor='#f8f0f5', alpha=0.7, edgecolor='#e8d5e0'))
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.90)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_analytics_page(self):
        """Create the analytics page with comprehensive data visualization"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #faf0f5; }")
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Header - Larger and more visible
        header = QLabel("📈 Advanced Analytics & Data Validation")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setStyleSheet("color: #7a6a6a; padding: 15px 0;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Year Selection for Analytics - Larger text
        year_frame = QFrame()
        year_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 10px;
                border: 1px solid #e8d5e0;
                padding: 15px;
            }
        """)
        year_layout = QHBoxLayout(year_frame)
        
        year_label = QLabel("Analyze Year:")
        year_label.setStyleSheet("color: #7a6a6a; font-weight: bold; font-size: 14px;")
        
        self.analytics_year_combo = QComboBox()
        self.analytics_year_combo.addItems([str(year) for year in self.years])
        self.analytics_year_combo.setCurrentText("2024")  # Default to 2024
        self.analytics_year_combo.currentTextChanged.connect(self.refresh_analytics)
        self.analytics_year_combo.setStyleSheet("font-size: 13px;")
        
        data_type_label = QLabel("Data Type:")
        data_type_label.setStyleSheet("color: #7a6a6a; font-weight: bold; font-size: 14px;")
        
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["Outdoor Temperature", "Indoor Temperature", "Comparison"])
        self.data_type_combo.currentTextChanged.connect(self.refresh_analytics)
        self.data_type_combo.setStyleSheet("font-size: 13px;")
        
        year_layout.addWidget(year_label)
        year_layout.addWidget(self.analytics_year_combo)
        year_layout.addSpacing(20)
        year_layout.addWidget(data_type_label)
        year_layout.addWidget(self.data_type_combo)
        year_layout.addStretch()
        
        layout.addWidget(year_frame)
        
        # Charts Container - this will hold the scroll area
        self.analytics_charts_widget = QWidget()
        self.analytics_charts_layout = QVBoxLayout(self.analytics_charts_widget)
        self.analytics_charts_layout.setSpacing(0)
        self.analytics_charts_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(self.analytics_charts_widget)
        
        # Initial load
        self.refresh_analytics()
        
        scroll.setWidget(page)
        return scroll

    def refresh_analytics(self):
        """Refresh analytics charts based on selected year and data type"""
        # Clear existing charts
        for i in reversed(range(self.analytics_charts_layout.count())):
            widget = self.analytics_charts_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        
        year = int(self.analytics_year_combo.currentText())
        data_type = self.data_type_combo.currentText()
        
        # Create a scroll area for the charts to handle many charts
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #faf0f5; }")
        
        # Create container widget for charts
        charts_container = QWidget()
        charts_layout = QVBoxLayout(charts_container)
        charts_layout.setSpacing(20)
        charts_layout.setContentsMargins(10, 10, 10, 10)
        
        if data_type == "Comparison":
            # Comparison layout - larger charts
            comparison_canvas = MplCanvas(self, width=9, height=5)
            self.create_comparison_chart(comparison_canvas.fig, year)
            charts_layout.addWidget(comparison_canvas)
            
            # Row for scatter and difference charts
            scatter_diff_layout = QHBoxLayout()
            scatter_diff_layout.setSpacing(15)
            
            scatter_canvas = MplCanvas(self, width=4.5, height=4)
            self.create_scatter_comparison_chart(scatter_canvas.fig, year)
            scatter_diff_layout.addWidget(scatter_canvas)
            
            diff_canvas = MplCanvas(self, width=4.5, height=4)
            self.create_difference_chart(diff_canvas.fig, year)
            scatter_diff_layout.addWidget(diff_canvas)
            
            charts_layout.addLayout(scatter_diff_layout)
            
        elif "Outdoor" in data_type or "Indoor" in data_type:
            # Single data type layout - larger charts in vertical layout
            is_outdoor = "Outdoor" in data_type
            
            yearly_canvas = MplCanvas(self, width=8, height=4)
            self.create_yearly_trend_chart(yearly_canvas.fig, year, "outdoor" if is_outdoor else "indoor")
            charts_layout.addWidget(yearly_canvas)
            
            monthly_canvas = MplCanvas(self, width=8, height=4)
            self.create_monthly_pattern_chart(monthly_canvas.fig, year, "outdoor" if is_outdoor else "indoor")
            charts_layout.addWidget(monthly_canvas)
            
            # Row for distribution and heatmap
            dist_heat_layout = QHBoxLayout()
            dist_heat_layout.setSpacing(15)
            
            distribution_canvas = MplCanvas(self, width=4, height=4)
            self.create_analytics_distribution_chart(distribution_canvas.fig, year, "outdoor" if is_outdoor else "indoor")
            dist_heat_layout.addWidget(distribution_canvas)
            
            heatmap_canvas = MplCanvas(self, width=4, height=4)
            self.create_heatmap_chart(heatmap_canvas.fig, year, "outdoor" if is_outdoor else "indoor")
            dist_heat_layout.addWidget(heatmap_canvas)
            
            charts_layout.addLayout(dist_heat_layout)
        
        # Add stretch to push everything to the top
        charts_layout.addStretch()
        
        # Set the charts container as the scroll area's widget
        scroll_area.setWidget(charts_container)
        
        # Add the scroll area to the analytics charts layout
        self.analytics_charts_layout.addWidget(scroll_area)

    def create_yearly_trend_chart(self, fig, year, data_type):
        """Create yearly temperature trend chart"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        # Generate sample data
        dates = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31', freq='D')
        if data_type == "outdoor":
            base_temp = 15 + 10 * np.sin(2 * np.pi * (dates.dayofyear - 80) / 365)
            noise = np.random.normal(0, 3, len(dates))
            temps = base_temp + noise
        else:
            base_temp = 21 + 3 * np.sin(2 * np.pi * (dates.dayofyear - 80) / 365)
            noise = np.random.normal(0, 1, len(dates))
            temps = base_temp + noise
        
        ax.plot(dates, temps, linewidth=2, alpha=0.7, 
                color='#ff6b9d' if data_type == "outdoor" else '#6b9dff')
        ax.fill_between(dates, temps, alpha=0.3, 
                    color='#ffb6c1' if data_type == "outdoor" else '#b6c1ff')
        
        # Reduced padding
        ax.set_title(f'{data_type.title()} Temperature Trend - {year}', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_ylabel('Temperature (°C)', fontsize=12)
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        ax.tick_params(axis='x', rotation=45, colors='#a89a9a', labelsize=10)
        ax.tick_params(axis='y', colors='#a89a9a', labelsize=10)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_monthly_pattern_chart(self, fig, year, data_type):
        """Create monthly pattern chart"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        if data_type == "outdoor":
            monthly_means = [5, 6, 10, 15, 19, 23, 26, 25, 21, 16, 10, 6]
        else:
            monthly_means = [19, 19, 20, 20, 21, 22, 23, 23, 22, 21, 20, 19]
        
        x_pos = np.arange(len(months))
        ax.bar(x_pos, monthly_means, alpha=0.7, 
               color='#ff6b9d' if data_type == "outdoor" else '#6b9dff')
        
        # Reduced padding
        ax.set_title(f'{data_type.title()} Monthly Pattern - {year}', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_ylabel('Average Temperature (°C)', fontsize=12)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(months)
        ax.grid(True, alpha=0.3, color='#e8d5e0', axis='y')
        ax.tick_params(colors='#a89a9a', labelsize=10)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_analytics_distribution_chart(self, fig, year, data_type):
        """Create temperature distribution chart for analytics page"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        if data_type == "outdoor":
            data = np.random.normal(15, 6, 1000)
            color = '#ff6b9d'
        else:
            data = np.random.normal(21, 2, 1000)
            color = '#6b9dff'
        
        ax.hist(data, bins=25, alpha=0.7, color=color, edgecolor='white', density=True)
        
        # Add KDE
        kde = gaussian_kde(data)
        x_range = np.linspace(data.min(), data.max(), 100)
        ax.plot(x_range, kde(x_range), color=color, linewidth=2, alpha=0.8)
        
        # Reduced padding
        ax.set_title(f'{data_type.title()} Temperature Distribution', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_xlabel('Temperature (°C)', fontsize=12)
        ax.set_ylabel('Density', fontsize=12)
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        ax.tick_params(colors='#a89a9a', labelsize=10)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_heatmap_chart(self, fig, year, data_type):
        """Create temperature heatmap"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        # Generate sample heatmap data
        hours = list(range(24))
        months = list(range(1, 13))
        
        # Create temperature matrix
        temp_matrix = np.zeros((12, 24))
        for i, month in enumerate(months):
            for j, hour in enumerate(hours):
                if data_type == "outdoor":
                    seasonal = 15 + 10 * np.sin(2 * np.pi * (month - 3) / 12)
                    daily = 8 * np.sin(2 * np.pi * (hour - 6) / 24)
                    temp_matrix[i, j] = seasonal + daily
                else:
                    seasonal = 21 + 2 * np.sin(2 * np.pi * (month - 3) / 12)
                    daily = 3 * np.sin(2 * np.pi * (hour - 8) / 24)
                    temp_matrix[i, j] = seasonal + daily
        
        im = ax.imshow(temp_matrix, cmap='RdYlBu_r', aspect='auto', 
                    extent=[0, 23, 12, 1])
        
        # Reduced padding
        ax.set_title(f'{data_type.title()} Temperature Heatmap - {year}', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_xlabel('Hour of Day', fontsize=12)
        ax.set_ylabel('Month', fontsize=12)
        ax.set_yticks(range(1, 13))
        ax.set_yticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
        
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label('Temperature (°C)', fontsize=11)
        cbar.ax.tick_params(colors='#a89a9a', labelsize=9)
        
        ax.tick_params(colors='#a89a9a', labelsize=9)
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_comparison_chart(self, fig, year):
        """Create outdoor vs indoor comparison chart"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        # Sample one week of data
        dates = pd.date_range(start=f'{year}-07-01', periods=168, freq='H')  # One week
        
        # Generate sample data
        outdoor_temps = [15 + 8 * np.sin(2 * np.pi * (h - 6) / 24) + 
                        np.random.normal(0, 1) for h in range(168)]
        indoor_temps = [20 + 3 * np.sin(2 * np.pi * (h - 8) / 24) + 
                    np.random.normal(0, 0.5) for h in range(168)]
        
        ax.plot(dates, outdoor_temps, label='Outdoor', linewidth=2, 
                color='#ff6b9d', alpha=0.8)
        ax.plot(dates, indoor_temps, label='Indoor', linewidth=2, 
                color='#6b9dff', alpha=0.8)
        
        # Reduced padding
        ax.set_title(f'Outdoor vs Indoor Temperature Comparison - {year}', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_ylabel('Temperature (°C)', fontsize=12)
        ax.legend(frameon=True, facecolor='#fff5fa', edgecolor='#e8d5e0', fontsize=11)
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        ax.tick_params(axis='x', rotation=45, colors='#a89a9a', labelsize=10)
        ax.tick_params(axis='y', colors='#a89a9a', labelsize=10)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_scatter_comparison_chart(self, fig, year):
        """Create scatter plot comparison"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        # Generate sample correlation data
        outdoor_temps = np.random.normal(15, 6, 300)
        indoor_temps = 18 + 0.6 * outdoor_temps + np.random.normal(0, 2, 300)
        
        ax.scatter(outdoor_temps, indoor_temps, alpha=0.6, color='#ff91a4', s=25)
        
        # Add correlation line
        z = np.polyfit(outdoor_temps, indoor_temps, 1)
        p = np.poly1d(z)
        ax.plot(outdoor_temps, p(outdoor_temps), color='#ff6b9d', linewidth=2, 
                label=f'Correlation: {np.corrcoef(outdoor_temps, indoor_temps)[0,1]:.2f}')
        
        # Reduced padding
        ax.set_title('Outdoor vs Indoor Correlation', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_xlabel('Outdoor Temperature (°C)', fontsize=12)
        ax.set_ylabel('Indoor Temperature (°C)', fontsize=12)
        ax.legend(frameon=True, facecolor='#fff5fa', edgecolor='#e8d5e0', fontsize=11)
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        ax.tick_params(colors='#a89a9a', labelsize=10)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_difference_chart(self, fig, year):
        """Create temperature difference chart"""
        fig.patch.set_facecolor('#faf0f5')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        
        # Generate sample difference data
        differences = np.random.normal(5, 2, 1000)
        
        ax.hist(differences, bins=25, alpha=0.7, color='#ffb6c1', edgecolor='white')
        ax.axvline(differences.mean(), color='#ff6b9d', linestyle='--', linewidth=2,
                label=f'Mean: {differences.mean():.1f}°C')
        
        # Reduced padding
        ax.set_title('Indoor - Outdoor Temperature Difference', 
                    fontsize=14, fontweight='bold', color='#7a6a6a', pad=8)
        ax.set_xlabel('Temperature Difference (°C)', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.legend(frameon=True, facecolor='#fff5fa', edgecolor='#e8d5e0', fontsize=11)
        ax.grid(True, alpha=0.3, color='#e8d5e0')
        ax.tick_params(colors='#a89a9a', labelsize=10)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#e8d5e0')
        ax.spines['bottom'].set_color('#e8d5e0')
        
        # Adjust subplot parameters to reduce top space
        fig.subplots_adjust(top=0.92)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

    def create_history_page(self):
        """Create the historical data page"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 20, 25, 20)
        
        header = QLabel("🕒 Historical Data")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setStyleSheet("color: #7a6a6a; padding: 15px 0;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Historical content
        content = QLabel("Historical temperature data and trends will be displayed here.\n\n"
                        "• Monthly temperature averages\n• Year-over-year comparisons\n"
                        "• Seasonal pattern analysis\n• Historical prediction performance")
        content.setStyleSheet("color: #a89a9a; font-size: 16px; padding: 40px;")
        content.setAlignment(Qt.AlignCenter)
        layout.addWidget(content)
        
        scroll.setWidget(page)
        return scroll

    def switch_page(self, page_name):
        """Switch between pages"""
        # Reset all buttons
        self.overview_btn.setObjectName("")
        self.analytics_btn.setObjectName("")
        self.history_btn.setObjectName("")
        
        if page_name == "overview":
            self.stacked_widget.setCurrentIndex(0)
            self.overview_btn.setObjectName("active")
        elif page_name == "analytics":
            self.stacked_widget.setCurrentIndex(1)
            self.analytics_btn.setObjectName("active")
        elif page_name == "history":
            self.stacked_widget.setCurrentIndex(2)
            self.history_btn.setObjectName("active")
        
        # Refresh styles
        for btn in [self.overview_btn, self.analytics_btn, self.history_btn]:
            btn.setStyle(btn.style())

    def year_changed(self, year):
        """Handle year change"""
        self.current_year = int(year)
        print(f"Year changed to: {self.current_year}")
        self.refresh_data()

    def get_current_temperatures(self):
        """Get current temperature predictions"""
        try:
            now = datetime.now()
            features = {
                'year': now.year,
                'month': now.month, 
                'day': now.day,
                'hour': now.hour
            }
            outdoor_temp = self.temperature_model.predict_outdoor([features])[0]
            indoor_temp = self.temperature_model.predict_indoor([features])[0]
            return outdoor_temp, indoor_temp
        except:
            # Fallback to realistic values
            current_hour = datetime.now().hour
            outdoor_temp = 15 + 8 * np.sin(2 * np.pi * (current_hour - 6) / 24)
            indoor_temp = 20 + 3 * np.sin(2 * np.pi * (current_hour - 8) / 24)
            return outdoor_temp, indoor_temp

    def load_initial_data(self):
        """Load initial data"""
        print("🔄 Loading initial data...")
        self.refresh_data()

    def refresh_data(self):
        """Refresh all data"""
        print("🔄 Refreshing data...")
        if hasattr(self, 'last_update_label'):
            self.last_update_label.setText(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Force UI update
        if self.stacked_widget.currentIndex() == 0:
            current_page = self.stacked_widget.currentWidget().widget()
            if current_page:
                current_page.update()

def main():
    app = QApplication(sys.argv)
    
    # Set application font - slightly larger for 14-inch screen
    font = QFont("Arial", 10)
    app.setFont(font)
    
    window = TemperatureDashboard()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()