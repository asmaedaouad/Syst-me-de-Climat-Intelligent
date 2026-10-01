import pandas as pd
import random
import os
from datetime import datetime

def indoor_temperature(outdoor_temp: float) -> float:
    """
    Estimate indoor temperature based on outdoor temperature.
    Adds or subtracts a small random offset for realism.
    """
    # For cold outdoor temps, indoors is slightly warmer
    if outdoor_temp < 18:
        offset = random.choice([2, 3])  # add 2 or 3 degrees
    # For hot outdoor temps, indoors is slightly cooler
    elif outdoor_temp > 28:
        offset = random.choice([-3, -4])  # subtract 3 or 4 degrees
    # Otherwise, roughly similar
    else:
        offset = random.choice([-1, 0, 1])
    
    return round(outdoor_temp + offset, 1)

def generate_indoor_temperatures_simple():
    """
    Generate indoor temperatures using simple rules
    """
    outdoor_folder = "data/outdoor_temp_data"
    indoor_folder = "data/indoor_temp_data"
    
    # Create indoor folder if it doesn't exist
    if not os.path.exists(indoor_folder):
        os.makedirs(indoor_folder)
        print(f"📁 Created folder: {indoor_folder}")
    
    # Get all outdoor temperature files
    outdoor_files = [f for f in os.listdir(outdoor_folder) if f.startswith('hourly_temperatures_') and f.endswith('.csv')]
    
    if not outdoor_files:
        print(f"❌ No outdoor temperature files found in {outdoor_folder}")
        return
    
    print("🏠 Generating Simple Indoor Temperatures...")
    print("=" * 40)
    print("Simple rules:")
    print("❄️  Cold (<18°C): +2 or +3°C")
    print("☀️  Hot (>28°C): -3 or -4°C") 
    print("🌤️  Mild: -1, 0, or +1°C")
    print("=" * 40)
    
    for outdoor_file in outdoor_files:
        # Extract year from filename
        year = outdoor_file.replace('hourly_temperatures_', '').replace('.csv', '')
        
        print(f"📊 Processing {year}...")
        
        # Read outdoor data
        outdoor_path = os.path.join(outdoor_folder, outdoor_file)
        outdoor_df = pd.read_csv(outdoor_path)
        
        # Generate indoor temperatures using simple function
        indoor_temps = []
        for outdoor_temp in outdoor_df['temperature']:
            indoor_temp = indoor_temperature(outdoor_temp)
            indoor_temps.append(indoor_temp)
        
        # Create indoor dataframe
        indoor_df = outdoor_df.copy()
        indoor_df['indoor_temperature'] = indoor_temps
        
        # Select only required columns
        indoor_result = indoor_df[['timestamp', 'year', 'month', 'day', 'hour', 'indoor_temperature']]
        
        # Save indoor data
        indoor_file = f"indoor_temperatures_{year}.csv"
        indoor_path = os.path.join(indoor_folder, indoor_file)
        indoor_result.to_csv(indoor_path, index=False)
        
        print(f"  ✅ Generated {len(indoor_result):,} indoor records")
        print(f"  📊 Indoor range: {indoor_result['indoor_temperature'].min():.1f}°C to {indoor_result['indoor_temperature'].max():.1f}°C")
        print(f"  💾 Saved to: {indoor_path}")
        
        # Show examples
        sample_outdoor = outdoor_df.head(3)
        for _, row in sample_outdoor.iterrows():
            indoor_temp = indoor_temperature(row['temperature'])
            print(f"  📅 Sample: Outside {row['temperature']}°C → Inside {indoor_temp}°C")

    print("=" * 40)
    print(f"✅ Successfully generated indoor temperatures for {len(outdoor_files)} years!")

def check_outdoor_data_exists():
    """Check if outdoor temperature data exists"""
    outdoor_folder = "data/outdoor_temp_data"
    
    if not os.path.exists(outdoor_folder):
        print(f"❌ Folder '{outdoor_folder}' does not exist!")
        return False
    
    outdoor_files = [f for f in os.listdir(outdoor_folder) if f.startswith('hourly_temperatures_') and f.endswith('.csv')]
    
    if not outdoor_files:
        print(f"❌ No outdoor temperature files found in '{outdoor_folder}'")
        return False
    
    print(f"✅ Found {len(outdoor_files)} outdoor temperature files in '{outdoor_folder}'")
    return True

# Test the function
def test_indoor_temperature():
    """Test the indoor temperature function"""
    print("🧪 Testing indoor temperature function:")
    test_temps = [5, 15, 22, 30, 35]
    for temp in test_temps:
        indoor = indoor_temperature(temp)
        print(f"  Outside {temp}°C → Inside {indoor}°C")

