import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures
import joblib
import os

def load_data():
    """Load outdoor and indoor temperature data from the new folder structure"""
    years = [2020, 2021, 2022, 2023, 2024, 2025]
    all_outdoor_data = []
    all_indoor_data = []

    for year in years:
        # Load outdoor data from outdoor_temp_data folder
        outdoor_filename = f'data/outdoor_temp_data/hourly_temperatures_{year}.csv'
        outdoor_df = pd.read_csv(outdoor_filename)
        all_outdoor_data.append(outdoor_df)

        # Load indoor data from indoor_temp_data folder
        indoor_filename = f'data/indoor_temp_data/indoor_temperatures_{year}.csv'
        indoor_df = pd.read_csv(indoor_filename)
        all_indoor_data.append(indoor_df)

    # Combine all years for outdoor data
    df_outdoor = pd.concat(all_outdoor_data, ignore_index=True)
    df_outdoor = df_outdoor.drop('timestamp', axis=1)

    # Combine all years for indoor data
    df_indoor = pd.concat(all_indoor_data, ignore_index=True)
    df_indoor = df_indoor.drop('timestamp', axis=1)

    return df_outdoor, df_indoor

def train_models():
    """Train both indoor and outdoor temperature models"""
    
    # Load data
    df_outdoor, df_indoor = load_data()
    
    # Split data - use 2020-2024 for training, 2025 for testing
    outdoor_train = df_outdoor[df_outdoor['year'] < 2025]   
    outdoor_test = df_outdoor[df_outdoor['year'] == 2025]

    indoor_train = df_indoor[df_indoor['year'] < 2025]
    indoor_test = df_indoor[df_indoor['year'] == 2025]

    # Prepare features and labels
    outdoor_features = outdoor_train.drop("temperature", axis=1)
    outdoor_labels = outdoor_train["temperature"]
    outdoor_test_features = outdoor_test.drop("temperature", axis=1)
    outdoor_test_labels = outdoor_test["temperature"]

    indoor_features = indoor_train.drop("indoor_temperature", axis=1)
    indoor_labels = indoor_train["indoor_temperature"]
    indoor_test_features = indoor_test.drop("indoor_temperature", axis=1)
    indoor_test_labels = indoor_test["indoor_temperature"]

    # Create model pipelines
    degree = 2

    outdoor_model = Pipeline([     
        ('poly', PolynomialFeatures(degree=degree)),
        ('forest', RandomForestRegressor())
    ])

    indoor_model = Pipeline([     
        ('poly', PolynomialFeatures(degree=degree)),
        ('forest', RandomForestRegressor())
    ])

    # Train models
    outdoor_model.fit(outdoor_features, outdoor_labels)
    indoor_model.fit(indoor_features, indoor_labels)

    # Save models
    os.makedirs('model/model_weights', exist_ok=True)
    joblib.dump(outdoor_model, 'model/model_weights/outdoor_model.pkl')
    joblib.dump(indoor_model, 'model/model_weights/indoor_model.pkl')

    # Evaluate models
    outdoor_score = outdoor_model.score(outdoor_test_features, outdoor_test_labels)
    indoor_score = indoor_model.score(indoor_test_features, indoor_test_labels)

    print(f"Outdoor model R² score: {outdoor_score:.4f}")
    print(f"Indoor model R² score: {indoor_score:.4f}")
    print("Models trained and saved successfully!")

    return outdoor_model, indoor_model

