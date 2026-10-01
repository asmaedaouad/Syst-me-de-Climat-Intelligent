import pandas as pd
import joblib
from datetime import datetime

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
            print("❌ Models not found. Please train models first.")
    
    def predict_outdoor(self, features):
        """Predict outdoor temperature using saved weights"""
        if self.outdoor_model is None:
            raise ValueError("Outdoor model not loaded. Train models first.")
        
        features = self._prepare_features(features)
        return self.outdoor_model.predict(features)
    
    def predict_indoor(self, features):
        """Predict indoor temperature using saved weights"""
        if self.indoor_model is None:
            raise ValueError("Indoor model not loaded. Train models first.")
        
        features = self._prepare_features(features)
        return self.indoor_model.predict(features)
    
    def predict_both(self, outdoor_features, indoor_features):
        """Predict both temperatures at once using saved weights"""
        return {
            'outdoor': self.predict_outdoor(outdoor_features),
            'indoor': self.predict_indoor(indoor_features)
        }
    
    def _prepare_features(self, features):
        """Ensure features have all required columns"""
        required_columns = ['year', 'month', 'day', 'hour']
        
        features_df = pd.DataFrame(features)
        for col in required_columns:
            if col not in features_df.columns:
                features_df[col] = 0
        
        return features_df[required_columns]


def main():
    """Main function to test the TemperatureModel with current datetime"""
    print("🧪 Testing Temperature Model Predictions")
    print("=" * 50)
    
    # Initialize the model
    model = TemperatureModel()
    
    # Get current datetime
    now = datetime.now()
    print(f"📅 Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Prepare features for current time
    current_features = [{
        'year': now.year,
        'month': now.month,
        'day': now.day,
        'hour': now.hour
    }]
    
    try:
        # Make predictions
        outdoor_pred = model.predict_outdoor(current_features)
        indoor_pred = model.predict_indoor(current_features)
        
        print("\n📊 Prediction Results:")
        print(f"🌡️  Outdoor Temperature Prediction: {outdoor_pred[0]:.2f}°C")
        print(f"🏠 Indoor Temperature Prediction: {indoor_pred[0]:.2f}°C")
        
        # Test the combined prediction method
        print("\n🔄 Testing combined prediction:")
        combined_pred = model.predict_both(current_features, current_features)
        print(f"🌡️  Combined Outdoor: {combined_pred['outdoor'][0]:.2f}°C")
        print(f"🏠 Combined Indoor: {combined_pred['indoor'][0]:.2f}°C")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")


if __name__ == "__main__":
    main()