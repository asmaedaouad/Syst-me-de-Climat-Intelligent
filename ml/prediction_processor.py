import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from model.model_predictor import TemperatureModel
from utils.data_storage import DataStorage

class PredictionProcessor:
    def __init__(self):
        self.model = TemperatureModel()
        self.storage = DataStorage()
    
    def simulate_indoor_temperature_dynamic(self, df_indoor, comfort_temp=22):
        """
        Simulate indoor temperature with HVAC control (auto mode only)
        """
        # HVAC configurations
        HEATER_LEVELS = {
            0: None, 1: 20.0, 2: 22.0, 3: 24.0, 4: 26.0, 5: 28.0
        }
        
        FAN_SPEEDS = {
            0: 0.0, 1: 0.3, 2: 0.6, 3: 0.9, 4: 1.2, 5: 1.5
        }
        
        current_temp = df_indoor.iloc[0]['predicted_temp']
        adjusted_temps = []
        heater_levels = []
        fan_levels = []
        heater_targets = []
        fan_cooling_power = []
        
        for _, row in df_indoor.iterrows():
            predicted_indoor_temp = row['predicted_temp']
            hour = row['hour']
            
            # HEATER: Auto logic only
            if current_temp < comfort_temp:
                temp_diff = comfort_temp - current_temp
                if temp_diff > 5: heater_power = 5
                elif temp_diff > 3: heater_power = 4
                elif temp_diff > 2: heater_power = 3
                elif temp_diff > 1: heater_power = 2
                elif temp_diff > 0.5: heater_power = 1
                else: heater_power = 0
            else:
                heater_power = 0

            # FAN: Auto logic only
            if current_temp > comfort_temp:
                temp_diff = current_temp - comfort_temp
                if temp_diff > 5: fan_speed = 5
                elif temp_diff > 3: fan_speed = 4
                elif temp_diff > 2: fan_speed = 3
                elif temp_diff > 1: fan_speed = 2
                elif temp_diff > 0.5: fan_speed = 1
                else: fan_speed = 0
            else:
                fan_speed = 0

            # Get target temperature for heater and cooling power for fan
            heater_target = HEATER_LEVELS[heater_power] if heater_power > 0 else None
            cooling_power = FAN_SPEEDS[fan_speed]

            # Update indoor temperature based on HVAC actions
            if heater_target is not None:
                temp_change = (heater_target - current_temp) * 0.3
                current_temp += temp_change
            
            if fan_speed > 0:
                current_temp -= cooling_power * 0.8
            
            # Natural temperature drift toward predicted temperature
            temp_drift = (predicted_indoor_temp - current_temp) * 0.1
            current_temp += temp_drift
            
            # Keep temperature within reasonable bounds
            current_temp = max(10, min(35, current_temp))
            
            # Store results
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
    
    def get_prediction_time_range(self):
        """
        Get time range for predictions: full day of tomorrow only
        """
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        
        # Start from 00:00 tomorrow
        start_datetime = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # End at 23:00 tomorrow
        end_datetime = tomorrow.replace(hour=23, minute=0, second=0, microsecond=0)
        
        print(f"🕒 Prediction time range: TOMORROW ONLY")
        print(f"   From: {start_datetime.strftime('%Y-%m-%d %H:%M')}")
        print(f"   To:   {end_datetime.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Total hours: 24")
        
        return start_datetime, end_datetime
    
    def generate_prediction_data(self, start_datetime, end_datetime, comfort_temp=22):
        """
        Generate prediction data for tomorrow only
        """
        print(f"📅 Generating predictions for tomorrow only...")
        
        # Create date range for predictions (hourly)
        date_range = pd.date_range(start=start_datetime, end=end_datetime, freq='H')
        
        # Prepare features for predictions
        outdoor_features = []
        indoor_features = []
        
        for dt in date_range:
            outdoor_features.append({
                'year': dt.year,
                'month': dt.month,
                'day': dt.day,
                'hour': dt.hour
            })
            
            indoor_features.append({
                'year': dt.year,
                'month': dt.month,
                'day': dt.day,
                'hour': dt.hour
            })
        
        outdoor_features_df = pd.DataFrame(outdoor_features)
        indoor_features_df = pd.DataFrame(indoor_features)
        
        # Get predictions from models
        print("🤖 Getting predictions from ML models...")
        outdoor_predictions = self.model.predict_outdoor(outdoor_features_df)
        indoor_predictions = self.model.predict_indoor(indoor_features_df)
        
        # Create indoor predictions dataframe for simulation
        indoor_pred_df = indoor_features_df.copy()
        indoor_pred_df['predicted_temp'] = indoor_predictions
        
        # Apply HVAC simulation (auto mode only)
        simulation_results = self.simulate_indoor_temperature_dynamic(
            indoor_pred_df,
            comfort_temp=comfort_temp
        )
        
        # Add outdoor predictions to results
        simulation_results['outdoor_temp'] = outdoor_predictions
        
        return simulation_results
    
    def process_predictions_for_website(self, comfort_temp=22):
        """
        Main method to process predictions for website
        Predicts for: full day of tomorrow only
        """
        print("🚀 Starting prediction processing for website...")
        print(f"🕒 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get prediction time range (tomorrow only)
        start_datetime, end_datetime = self.get_prediction_time_range()
        
        # Generate predictions
        predictions_df = self.generate_prediction_data(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            comfort_temp=comfort_temp
        )
        
        # Store predictions in database
        self.storage.store_predictions(predictions_df)
        
        print(f"✅ Processed {len(predictions_df)} predictions for website")
        print(f"📊 Stored predictions for: {start_datetime.strftime('%Y-%m-%d')}")
        
        return predictions_df

if __name__ == "__main__":
    processor = PredictionProcessor()
    
    # Process predictions for tomorrow only
    results = processor.process_predictions_for_website(
        comfort_temp=22
    )