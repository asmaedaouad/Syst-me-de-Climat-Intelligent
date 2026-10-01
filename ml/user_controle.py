import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.data_storage import DataStorage

class UserControl:
    def __init__(self):
        self.storage = DataStorage()
    
    def simulate_indoor_temperature_dynamic(self, df_indoor, comfort_temp=22, user_heater_override=None, user_fan_override=None, hour_to_override=None):
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
    
    def get_predictions_from_database(self, date=None):
        """
        Get predictions from database for a specific date
        If no date specified, gets predictions for tomorrow
        """
        if date is None:
            # Default to tomorrow
            date = (datetime.now() + timedelta(days=1)).date()
        
        print(f"📊 Retrieving predictions from database for {date}...")
        
        # Get predictions from database
        predictions_df = self.storage.get_predictions_for_website(days=2)
        
        if predictions_df.empty:
            print(f"❌ No predictions found in database for {date}")
            return None
        
        # Filter for the specific date
        date_predictions = predictions_df[
            (predictions_df['year'] == date.year) & 
            (predictions_df['month'] == date.month) & 
            (predictions_df['day'] == date.day)
        ]
        
        if date_predictions.empty:
            print(f"❌ No predictions found for {date}")
            return None
        
        print(f"✅ Found {len(date_predictions)} predictions for {date}")
        return date_predictions
    
    def apply_user_overrides(self, predictions_df, comfort_temp=22, user_overrides=None):
        """
        Apply user overrides to predictions and recalculate
        """
        print("🔄 Applying user overrides...")
        
        user_overrides = user_overrides or {}
        
        # Prepare indoor dataframe for simulation
        indoor_df = predictions_df[['year', 'month', 'day', 'hour', 'predicted_temp']].copy()
        
        # Apply simulation with user overrides
        modified_results = self.simulate_indoor_temperature_dynamic(
            indoor_df,
            comfort_temp=comfort_temp,
            user_heater_override=user_overrides.get('heater_override'),
            user_fan_override=user_overrides.get('fan_override'),
            hour_to_override=user_overrides.get('override_hours')
        )
        
        # Update the original predictions with modified results
        predictions_df['adjusted_temp'] = modified_results['adjusted_temp']
        predictions_df['heater_level'] = modified_results['heater_level']
        predictions_df['fan_speed'] = modified_results['fan_speed']
        predictions_df['heater_target'] = modified_results['heater_target']
        predictions_df['fan_cooling_power'] = modified_results['fan_cooling_power']
        predictions_df['temperature_difference'] = modified_results['temperature_difference']
        
        print("✅ User overrides applied successfully!")
        return predictions_df
    
    def store_modified_predictions(self, predictions_df):
        """
        Store modified predictions back to database
        This will replace/update the existing predictions
        """
        print("💾 Storing modified predictions to database...")
        
        # Clear existing predictions for these dates
        dates_to_clear = predictions_df[['year', 'month', 'day']].drop_duplicates()
        
        for _, date_row in dates_to_clear.iterrows():
            self.storage.clear_predictions_for_date(
                date_row['year'], 
                date_row['month'], 
                date_row['day']
            )
        
        # Store modified predictions
        success = self.storage.store_predictions(predictions_df)
        
        if success:
            print("✅ Modified predictions stored successfully!")
        else:
            print("❌ Failed to store modified predictions")
        
        return success
    
    def process_user_control(self, date=None, comfort_temp=22, user_overrides=None):
        """
        Main method to process user control
        """
        print("🎛️  PROCESSING USER CONTROL...")
        print("=" * 50)
        
        # Step 1: Get predictions from database
        predictions_df = self.get_predictions_from_database(date)
        
        if predictions_df is None:
            print("❌ Cannot proceed - no predictions found")
            return None
        
        # Step 2: Apply user overrides
        modified_predictions = self.apply_user_overrides(
            predictions_df, 
            comfort_temp=comfort_temp,
            user_overrides=user_overrides
        )
        
        # Step 3: Store modified predictions back to database
        success = self.store_modified_predictions(modified_predictions)
        
        if success:
            print(f"🎉 User control processing completed successfully!")
            print(f"📊 Modified {len(modified_predictions)} predictions")
        else:
            print("❌ User control processing failed")
        
        return modified_predictions if success else None

# Example usage
if __name__ == "__main__":
    controller = UserControl()
    
    # Example user overrides (from website interface)
    user_overrides = {
        'heater_override': 3,           # Set heater to level 3
        'fan_override': None,           # Auto mode for fan
        'override_hours': [9, 10, 11, 12]  # Apply overrides at 9AM-12PM
    }
    
    # Process user control for tomorrow
    results = controller.process_user_control(
        date=None,  # Tomorrow
        comfort_temp=21,  # User changed comfort temperature
        user_overrides=user_overrides
    )