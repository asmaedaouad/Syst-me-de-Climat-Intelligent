import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

class TemperatureGenerator:
    def __init__(self):
        # Load parameters from references folder
        with open("data/references/temperature_params.json", "r") as f:
            self.real_monthly = json.load(f)
        
        with open("data/references/avg_temp_params.json", "r") as f:
            self.avg_monthly = json.load(f)
        
    def generate_daily_temperature_curve(self, daily_min, daily_max, daily_swing):
        """Generate realistic 24-hour temperature curve - FIXED TIMING"""
        hours = np.arange(24)
        
        # FIXED: Hottest at 1 PM (hour 13), coldest at 6 AM (hour 6)
        temp_6am = daily_min    # Coldest at 6 AM
        temp_1pm = daily_max    # Hottest at 1 PM
        temp_8pm = daily_min + (daily_max - daily_min) * 0.4  # Evening cooling
        temp_midnight = daily_min + (daily_max - daily_min) * 0.2  # Late night
        
        temperatures = []
        
        for hour in hours:
            if hour <= 6:  # Midnight to 6 AM - fast cooling
                if hour <= 3:
                    # Fast drop from 8 PM to midnight
                    t = temp_8pm + (temp_midnight - temp_8pm) * ((hour - 0) / 3.0)
                else:
                    # Fast drop from midnight to 6 AM
                    t = temp_midnight + (temp_6am - temp_midnight) * ((hour - 3) / 3.0)
                    
            elif hour <= 13:  # 6 AM to 1 PM - quick warming
                # Fast rise from 6 AM to 1 PM
                t = temp_6am + (temp_1pm - temp_6am) * ((hour - 6) / 7.0)
                
            else:  # 1 PM to midnight - gradual then fast cooling
                if hour <= 20:
                    # Gradual cooling from 1 PM to 8 PM
                    t = temp_1pm + (temp_8pm - temp_1pm) * ((hour - 13) / 7.0)
                else:
                    # Fast cooling from 8 PM to midnight
                    t = temp_8pm + (temp_midnight - temp_8pm) * ((hour - 20) / 4.0)
            
            temperatures.append(t)
        
        return np.array(temperatures)
    
    def smooth_monthly_progression(self, month, day_progress):
        """More gradual temperature changes throughout the month"""
        # Define monthly temperature profiles
        monthly_profiles = {
            # Winter months
            12: {"start_temp": 0.7, "end_temp": 0.3, "curve": "linear"},  # Gradual cooling
            1: {"start_temp": 0.3, "end_temp": 0.4, "curve": "u"},        # Coldest in middle
            2: {"start_temp": 0.4, "end_temp": 0.7, "curve": "linear"},   # Gradual warming
            
            # Spring months  
            3: {"start_temp": 0.7, "end_temp": 0.9, "curve": "linear"},   # Steady warming
            4: {"start_temp": 0.9, "end_temp": 1.0, "curve": "ease_out"}, # Peak warming
            5: {"start_temp": 1.0, "end_temp": 0.9, "curve": "ease_in"},  # Slight cooling
            
            # Summer months
            6: {"start_temp": 0.9, "end_temp": 1.0, "curve": "linear"},   # Warming up
            7: {"start_temp": 1.0, "end_temp": 1.0, "curve": "flat"},     # Peak heat
            8: {"start_temp": 1.0, "end_temp": 0.8, "curve": "ease_out"}, # Gradual cooling
            
            # Autumn months
            9: {"start_temp": 0.8, "end_temp": 0.6, "curve": "linear"},   # Cooling
            10: {"start_temp": 0.6, "end_temp": 0.4, "curve": "linear"},  # More cooling
            11: {"start_temp": 0.4, "end_temp": 0.3, "curve": "ease_in"}  # Gentle cooling
        }
        
        if month not in monthly_profiles:
            return 0.5  # Default
        
        profile = monthly_profiles[month]
        start = profile["start_temp"]
        end = profile["end_temp"]
        curve_type = profile["curve"]
        
        # Apply different curve types for smooth transitions
        if curve_type == "linear":
            return start + (end - start) * day_progress
        elif curve_type == "ease_in":
            return start + (end - start) * (day_progress ** 2)
        elif curve_type == "ease_out":
            return start + (end - start) * (1 - (1 - day_progress) ** 2)
        elif curve_type == "u":  # Coldest in middle (winter)
            return start + (end - start) * (1 - abs(day_progress - 0.5) * 2)
        elif curve_type == "flat":  # Consistent temperature
            return (start + end) / 2
        else:
            return start + (end - start) * day_progress
    
    def get_monthly_temperature_range(self, year, month, day):
        """Get realistic min/max for a specific day considering seasonal trends"""
        year_str = str(year)
        month_str = str(month)
        
        # Get the actual monthly boundaries
        monthly_min = self.real_monthly[year_str][month_str]["min_temp"]
        monthly_max = self.real_monthly[year_str][month_str]["max_temp"]
        daily_swing = self.avg_monthly[month_str]["daily_swing"]
        
        # Calculate day's position in month (0 to 1)
        if month == 12:
            days_in_month = 31
        else:
            next_month = month + 1
            days_in_month = (datetime(year, next_month, 1) - datetime(year, month, 1)).days
        
        day_progress = (day - 1) / (days_in_month - 1) if days_in_month > 1 else 0.5
        
        # Use smooth monthly progression
        temp_factor = self.smooth_monthly_progression(month, day_progress)
        
        # Calculate daily range within monthly bounds
        daily_avg = monthly_min + (monthly_max - monthly_min) * temp_factor
        
        # Apply daily swing
        daily_max = daily_avg + daily_swing / 2
        daily_min = daily_avg - daily_swing / 2
        
        # Ensure we don't exceed monthly boundaries
        daily_min = max(monthly_min, daily_min)
        daily_max = min(monthly_max, daily_max)
        
        # Ensure min < max
        daily_min = min(daily_min, daily_max - 1.0)
        
        return daily_min, daily_max, daily_swing
    
    def generate_year_data(self, year):
        """Generate complete hourly data for a year"""
        records = []
        current_date = datetime(year, 1, 1)
        
        while current_date.year == year:
            month = current_date.month
            day = current_date.day
            
            # Skip invalid months (like Dec 2025 with 0,0)
            if (year == 2025 and month == 12 and 
                self.real_monthly[str(year)][str(month)]["min_temp"] == 0):
                current_date += timedelta(days=1)
                continue
            
            # Get daily temperature range
            daily_min, daily_max, daily_swing = self.get_monthly_temperature_range(
                year, month, day
            )
            
            # Generate 24-hour curve
            hourly_temps = self.generate_daily_temperature_curve(
                daily_min, daily_max, daily_swing
            )
            
            # Create records for each hour
            for hour, temp in enumerate(hourly_temps):
                timestamp = current_date.replace(hour=hour)
                records.append({
                    'timestamp': timestamp,
                    'year': year,
                    'month': month,
                    'day': day,
                    'hour': hour,
                    'temperature': round(temp, 2)
                })
            
            current_date += timedelta(days=1)
        
        return pd.DataFrame(records)
    
    def generate_all_years(self):
        """Generate data for all years and save separate CSV files"""
        output_dir = "data/outdoor_temp_data"
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        years = [int(yr) for yr in self.real_monthly.keys()]
        
        for year in sorted(years):
            print(f"Generating {year}...")
            
            df = self.generate_year_data(year)
            
            # Save to CSV
            filename = os.path.join(output_dir, f"hourly_temperatures_{year}.csv")
            df.to_csv(filename, index=False)
            
            print(f"  ✓ {len(df):,} records | "
                  f"Temp range: {df['temperature'].min():.1f}°C to {df['temperature'].max():.1f}°C")
            
            # Show November progression for 2025 with hourly sample
            if year == 2025 and 11 in df['month'].unique():
                nov_data = df[df['month'] == 11]
                sample_day = 23
                day_data = nov_data[nov_data['day'] == sample_day]
                if len(day_data) > 0:
                    print(f"  November {sample_day}, 2025 Sample:")
                    # Show key hours to verify timing
                    key_hours = [0, 6, 9, 12, 13, 15, 18, 21]
                    for hour in key_hours:
                        temp = day_data[day_data['hour'] == hour]['temperature'].values[0]
                        am_pm = "AM" if hour < 12 else "PM"
                        hour_12 = hour if hour <= 12 else hour - 12
                        print(f"    {hour_12:2d}{am_pm}: {temp:5.1f}°C")

