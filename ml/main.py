"""
Main Orchestrator - The center of everything
Automatically checks, generates data, stores to Azure, trains models, and generates predictions
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

def check_data_folders():
    """
    Check if data folders are empty (no data generated yet)
    Returns True if data needs to be generated, False if data already exists
    """
    outdoor_folder = "data/outdoor_temp_data"
    indoor_folder = "data/indoor_temp_data"
    
    # Check if folders exist and have CSV files
    outdoor_has_data = os.path.exists(outdoor_folder) and any(f.endswith('.csv') for f in os.listdir(outdoor_folder))
    indoor_has_data = os.path.exists(indoor_folder) and any(f.endswith('.csv') for f in os.listdir(indoor_folder))
    
    print("📁 Checking data folders...")
    print(f"   Outdoor data: {'✅ Found' if outdoor_has_data else '❌ Missing'}")
    print(f"   Indoor data:  {'✅ Found' if indoor_has_data else '❌ Missing'}")
    
    # Return True if either folder is missing data
    return not (outdoor_has_data and indoor_has_data)

def generate_outdoor_data():
    """Generate outdoor temperature data"""
    print("\n🌡️  GENERATING OUTDOOR TEMPERATURE DATA...")
    print("=" * 50)
    
    try:
        from simulation.temperature_generator import TemperatureGenerator
        generator = TemperatureGenerator()
        generator.generate_all_years()
        print("✅ Outdoor data generated successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to generate outdoor data: {e}")
        return False

def generate_indoor_data():
    """Generate indoor temperature data"""
    print("\n🏠 GENERATING INDOOR TEMPERATURE DATA...")
    print("=" * 50)
    
    try:
        from simulation.indoor_temp_generator import generate_indoor_temperatures_simple
        generate_indoor_temperatures_simple()
        print("✅ Indoor data generated successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to generate indoor data: {e}")
        return False

def store_data_to_azure():
    """Store generated data to Azure SQL and Blob Storage"""
    print("\n💾 STORING DATA TO AZURE...")
    print("=" * 50)
    
    try:
        from utils.data_storage import DataStorage
        storage = DataStorage()
        
        # Define years to process
        years = [2020, 2021, 2022, 2023, 2024, 2025]
        
        # Process all years
        storage.process_all_years(years)
        print("✅ Data stored to Azure successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to store data to Azure: {e}")
        return False

def train_ml_models():
    """Train machine learning models"""
    print("\n🤖 TRAINING MACHINE LEARNING MODELS...")
    print("=" * 50)
    
    try:
        from model.train_models import train_models
        outdoor_model, indoor_model = train_models()
        print("✅ Models trained successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to train models: {e}")
        return False

def validate_data():
    """Validate the generated data"""
    print("\n🔍 VALIDATING GENERATED DATA...")
    print("=" * 50)
    
    try:
        from utils.visualization import validate_temperature_data
        
        # Validate latest year for both outdoor and indoor
        print("Validating outdoor data...")
        validate_temperature_data(2024, "outdoor")
        
        print("\nValidating indoor data...")
        validate_temperature_data(2024, "indoor")
        
        print("✅ Data validation completed!")
        return True
    except Exception as e:
        print(f"❌ Data validation failed: {e}")
        return False

def generate_predictions():
    """Generate predictions for website"""
    print("\n🔮 GENERATING PREDICTIONS FOR WEBSITE...")
    print("=" * 50)
    
    try:
        from prediction_processor import PredictionProcessor
        processor = PredictionProcessor()
        
        # Generate predictions for tomorrow
        results = processor.process_predictions_for_website(
            comfort_temp=22
        )
        
        print("✅ Predictions generated and stored successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to generate predictions: {e}")
        return False

def main():
    """
    Main orchestrator - trains models, prepares data, and generates predictions
    """
    print("🚀 TEMPERATURE PROJECT - MAIN ORCHESTRATOR")
    print("=" * 60)
    
    # Track success of each step
    steps_success = {}
    
    # Step 1: Check if data needs to be generated
    needs_data_generation = check_data_folders()
    
    if needs_data_generation:
        print("\n📊 DATA GENERATION REQUIRED - Starting pipeline...")
        
        # Step 2: Generate outdoor data
        steps_success['outdoor_generation'] = generate_outdoor_data()
        
        # Step 3: Generate indoor data
        steps_success['indoor_generation'] = generate_indoor_data()
        
        # Step 4: Store data to Azure
        if steps_success['outdoor_generation'] and steps_success['indoor_generation']:
            steps_success['azure_storage'] = store_data_to_azure()
        else:
            print("❌ Skipping Azure storage due to data generation failures")
            steps_success['azure_storage'] = False
    else:
        print("\n📊 DATA ALREADY EXISTS - Skipping generation...")
        steps_success['outdoor_generation'] = True
        steps_success['indoor_generation'] = True
        steps_success['azure_storage'] = True
    
    # Step 5: Train ML models (always run this to ensure models are up-to-date)
    steps_success['model_training'] = train_ml_models()
    
    # Step 6: Validate data (optional)
    steps_success['data_validation'] = validate_data()
    
    # Step 7: Generate predictions for website
    steps_success['predictions'] = generate_predictions()
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    
    for step, success in steps_success.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{step.replace('_', ' ').title():<20} : {status}")
    
    # Overall status
    all_success = all(steps_success.values())
    if all_success:
        print("\n🎊 ALL STEPS COMPLETED SUCCESSFULLY! 🎊")
        print("Your system is ready! Models trained and predictions generated! 🚀")
    else:
        print(f"\n⚠️  {sum(steps_success.values())}/{len(steps_success)} steps completed successfully")
        print("Check the errors above and run again.")
    
    print("\n📋 NEXT STEPS:")
    print("1. Website can now retrieve predictions from database")
    print("2. Run 'python main.py' again to regenerate everything")
    print("3. Run 'python prediction_processor.py' for new predictions only")
    print("4. Check Azure Portal for stored data")

def train_only():
    """
    Train models only - skip data generation and storage
    """
    print("🤖 TRAINING MODELS ONLY...")
    print("=" * 50)
    
    success = train_ml_models()
    
    if success:
        print("✅ Models trained successfully!")
    else:
        print("❌ Failed to train models")

def predictions_only():
    """
    Generate predictions only - skip everything else
    """
    print("🔮 GENERATING PREDICTIONS ONLY...")
    print("=" * 50)
    
    success = generate_predictions()
    
    if success:
        print("✅ Predictions generated successfully!")
    else:
        print("❌ Failed to generate predictions")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Temperature Project Orchestrator')
    parser.add_argument('--train-only', action='store_true', help='Train models only (skip data generation and storage)')
    parser.add_argument('--predictions-only', action='store_true', help='Generate predictions only (skip everything else)')
    
    args = parser.parse_args()
    
    if args.train_only:
        train_only()
    elif args.predictions_only:
        predictions_only()
    else:
        main()