import pyodbc
import csv
import os
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

# Azure SQL Database configuration
server = os.environ['AZURE_SQL_SERVER']
database = os.environ['AZURE_SQL_DATABASE']
username = os.environ['AZURE_SQL_USER']
password = os.environ['AZURE_SQL_PASSWORD']
driver = '{ODBC Driver 18 for SQL Server}'

# Update your connection string with explicit SSL settings
conn_str = (
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};'
    f'PWD={password};Encrypt=yes;TrustServerCertificate=no;'
    f'Connection Timeout=30;SSL=required;'
)

# Azure Blob Storage configuration
blob_connection_string = os.environ['AZURE_BLOB_CONNECTION_STRING']
container_name = os.environ.get("AZURE_BLOB_CONTAINER", "csvdatafile")

class DataStorage:
    def __init__(self):
        self.conn_str = conn_str
        self.blob_connection_string = blob_connection_string
        self.container_name = container_name
    
    def create_outdoor_table_if_not_exists(self, cursor):
        """Create the outdoor temperature table if it doesn't exist"""
        table_name = 'OutdoorTempData2020_2025'
        cursor.execute(f"""
        IF OBJECT_ID('{table_name}', 'U') IS NULL
        CREATE TABLE {table_name} (
            timestamp DATETIME,
            year INT,
            month INT,
            day INT,
            hour INT,
            temperature FLOAT
        )
        """)
    
    def create_indoor_table_if_not_exists(self, cursor):
        """Create the indoor temperature table if it doesn't exist"""
        table_name = 'IndoorTempData2020_2025'
        cursor.execute(f"""
        IF OBJECT_ID('{table_name}', 'U') IS NULL
        CREATE TABLE {table_name} (
            id INT IDENTITY(1,1) PRIMARY KEY,
            timestamp DATETIME,
            year INT,
            month INT,
            day INT,
            hour INT,
            indoor_temp FLOAT,
            heater_level INT,
            fan_level INT
        )
        """)
    
    def create_predictions_table_if_not_exists(self, cursor):
        """Create the predictions table if it doesn't exist"""
        table_name = 'TemperaturePredictions'
        cursor.execute(f"""
        IF OBJECT_ID('{table_name}', 'U') IS NULL
        CREATE TABLE {table_name} (
            id INT IDENTITY(1,1) PRIMARY KEY,
            year INT,
            month INT,
            day INT,
            hour INT,
            predicted_temp FLOAT,
            adjusted_temp FLOAT,
            outdoor_temp FLOAT,
            heater_level INT,
            fan_speed INT,
            comfort_temp FLOAT,
            prediction_date DATETIME DEFAULT GETDATE()
        )
        """)
    
    def calculate_hvac_levels(self, indoor_temp, comfort_temp=22):
        """
        Calculate heater and fan levels based on indoor temperature and comfort temperature
        Uses 5-level logic
        """
        # Heater logic (when it's too cold)
        if indoor_temp < comfort_temp:
            temp_diff = comfort_temp - indoor_temp
            if temp_diff > 5:
                heater_level = 5  # Very cold - max heat
            elif temp_diff > 3:
                heater_level = 4  # Cold - high heat
            elif temp_diff > 2:
                heater_level = 3  # Cool - medium heat
            elif temp_diff > 1:
                heater_level = 2  # Slightly cool - low heat
            elif temp_diff > 0.5:
                heater_level = 1  # Bit cool - minimal heat
            else:
                heater_level = 0  # Close enough - no heat
        else:
            heater_level = 0  # No heating needed

        # Fan logic (when it's too hot)
        if indoor_temp > comfort_temp:
            temp_diff = indoor_temp - comfort_temp
            if temp_diff > 5:
                fan_level = 5  # Very hot - max speed
            elif temp_diff > 3:
                fan_level = 4  # Hot - very high speed
            elif temp_diff > 2:
                fan_level = 3  # Warm - high speed
            elif temp_diff > 1:
                fan_level = 2  # Slightly warm - medium speed
            elif temp_diff > 0.5:
                fan_level = 1  # Bit warm - low speed
            else:
                fan_level = 0  # Close enough - fan off
        else:
            fan_level = 0  # No cooling needed

        return heater_level, fan_level
    
    def clear_existing_outdoor_data(self, year=None):
        """
        Clear existing data from the outdoor table
        If year is specified, clear only that year's data
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            if year:
                cursor.execute("DELETE FROM OutdoorTempData2020_2025 WHERE year = ?", year)
                print(f"🧹 Cleared existing outdoor data for year {year}")
            else:
                cursor.execute("DELETE FROM OutdoorTempData2020_2025")
                print("🧹 Cleared all existing outdoor data")
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error clearing outdoor data: {str(e)}")
    
    def clear_existing_indoor_data(self, year=None):
        """
        Clear existing data from the indoor table
        If year is specified, clear only that year's data
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            if year:
                cursor.execute("DELETE FROM IndoorTempData2020_2025 WHERE year = ?", year)
                print(f"🧹 Cleared existing indoor data for year {year}")
            else:
                cursor.execute("DELETE FROM IndoorTempData2020_2025")
                print("🧹 Cleared all existing indoor data")
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error clearing indoor data: {str(e)}")
    
    def upload_outdoor_csv_to_azure_sql(self, csv_file_path, year):
        """
        Upload outdoor CSV data to Azure SQL Database
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            cursor.fast_executemany = True
            
            # Create table if it doesn't exist
            self.create_outdoor_table_if_not_exists(cursor)
            conn.commit()
            
            # Read CSV file
            records = []
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Parse timestamp
                    timestamp_obj = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    
                    # Handle temperature value
                    temp_value = float(row['temperature']) if row['temperature'] else None
                    
                    records.append((
                        timestamp_obj,
                        int(row['year']),
                        int(row['month']),
                        int(row['day']),
                        int(row['hour']),
                        temp_value
                    ))
            
            # Prepare insert query
            insert_query = """
            INSERT INTO OutdoorTempData2020_2025 (timestamp, year, month, day, hour, temperature)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            
            # Insert into database
            print(f"💾 Inserting {len(records)} outdoor records into Azure SQL...")
            cursor.executemany(insert_query, records)
            conn.commit()
            
            cursor.close()
            conn.close()
            
            print(f"✅ Successfully uploaded {len(records)} outdoor records to Azure SQL Database!")
            return True
            
        except Exception as e:
            print(f"❌ Error uploading outdoor data to Azure SQL: {str(e)}")
            return False
    
    def upload_indoor_csv_to_azure_sql(self, csv_file_path, year):
        """
        Upload indoor CSV data to Azure SQL Database with dynamically calculated HVAC levels
        The CSV files remain unchanged, only the SQL table gets the extra columns
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            cursor.fast_executemany = True
            
            # Create table if it doesn't exist (with HVAC columns)
            self.create_indoor_table_if_not_exists(cursor)
            conn.commit()
            
            # Read CSV file (which only has basic columns)
            records = []
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Parse timestamp
                    timestamp_obj = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    
                    # Handle indoor temperature value
                    indoor_temp_value = float(row['indoor_temperature']) if row['indoor_temperature'] else None
                    
                    # Calculate HVAC levels based on indoor temperature
                    heater_level, fan_level = self.calculate_hvac_levels(indoor_temp_value)
                    
                    records.append((
                        timestamp_obj,
                        int(row['year']),
                        int(row['month']),
                        int(row['day']),
                        int(row['hour']),
                        indoor_temp_value,
                        heater_level,
                        fan_level
                    ))
            
            # Prepare insert query (includes HVAC columns)
            insert_query = """
            INSERT INTO IndoorTempData2020_2025 (timestamp, year, month, day, hour, indoor_temperature, heater_level, fan_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Insert into database
            print(f"💾 Inserting {len(records)} indoor records with HVAC levels into Azure SQL...")
            cursor.executemany(insert_query, records)
            conn.commit()
            
            cursor.close()
            conn.close()
            
            print(f"✅ Successfully uploaded {len(records)} indoor records with HVAC levels to Azure SQL Database!")
            return True
            
        except Exception as e:
            print(f"❌ Error uploading indoor data to Azure SQL: {str(e)}")
            return False
    
    def store_predictions(self, predictions_df):
        """
        Store prediction results for website retrieval
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            cursor.fast_executemany = True
            
            # Create predictions table if it doesn't exist
            self.create_predictions_table_if_not_exists(cursor)
            conn.commit()
            
            # Prepare records for insertion
            records = []
            for _, row in predictions_df.iterrows():
                records.append((
                    int(row['year']),
                    int(row['month']),
                    int(row['day']),
                    int(row['hour']),
                    float(row['predicted_temp']) if 'predicted_temp' in row else None,
                    float(row['adjusted_temp']) if 'adjusted_temp' in row else None,
                    float(row['outdoor_temp']) if 'outdoor_temp' in row else None,
                    int(row['heater_level']) if 'heater_level' in row else 0,
                    int(row['fan_speed']) if 'fan_speed' in row else 0,
                    float(row['comfort_temp']) if 'comfort_temp' in row else 22.0
                ))
            
            # Prepare insert query
            insert_query = """
            INSERT INTO TemperaturePredictions (year, month, day, hour, predicted_temp, adjusted_temp, outdoor_temp, heater_level, fan_speed, comfort_temp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Insert into database
            print(f"💾 Storing {len(records)} prediction records...")
            cursor.executemany(insert_query, records)
            conn.commit()
            
            cursor.close()
            conn.close()
            
            print(f"✅ Successfully stored {len(records)} prediction records!")
            return True
            
        except Exception as e:
            print(f"❌ Error storing predictions: {str(e)}")
            return False
    
    def get_predictions_for_website(self, days=1):
        """
        Retrieve predictions for website display
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            
            query = """
            SELECT * FROM TemperaturePredictions 
            WHERE prediction_date >= DATEADD(day, -?, GETDATE())
            ORDER BY year, month, day, hour
            """
            
            df = pd.read_sql(query, conn, params=[days])
            conn.close()
            
            print(f"✅ Retrieved {len(df)} predictions for website")
            return df
            
        except Exception as e:
            print(f"❌ Error retrieving predictions: {str(e)}")
            return pd.DataFrame()
    
    def upload_csv_to_blob_storage(self, local_file_path, year, data_type="outdoor"):
        """
        Upload a CSV file to Azure Blob Storage
        """
        try:
            # Create blob name with year and data type for better organization
            if data_type == "indoor":
                blob_name = f"indoor_temperature_data_{year}.csv"
            else:
                blob_name = f"outdoor_temperature_data_{year}.csv"
            
            # Connect to Azure Blob Storage
            blob_service_client = BlobServiceClient.from_connection_string(self.blob_connection_string)
            blob_client = blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)

            # Upload the file
            with open(local_file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

            print(f"☁️ {data_type.capitalize()} CSV uploaded successfully to Azure Blob Storage as {blob_name}!")
            return True
            
        except Exception as e:
            print(f"❌ Error uploading {data_type} data to Azure Blob Storage: {str(e)}")
            return False
    
    def process_outdoor_year_data(self, year):
        """
        Process a single year's outdoor data
        """
        csv_file_path = f"data/outdoor_temp_data/hourly_temperatures_{year}.csv"
        
        if not os.path.exists(csv_file_path):
            print(f"❌ Outdoor CSV file not found: {csv_file_path}")
            return False
        
        print(f"🚀 Processing outdoor data for year {year}...")
        
        # Step 1: Clear existing outdoor data for this year
        self.clear_existing_outdoor_data(year)
        
        # Step 2: Upload to Azure SQL Database
        sql_success = self.upload_outdoor_csv_to_azure_sql(csv_file_path, year)
        
        # Step 3: Upload to Azure Blob Storage
        blob_success = self.upload_csv_to_blob_storage(csv_file_path, year, "outdoor")
        
        if sql_success and blob_success:
            print(f"✅ Outdoor year {year} processed successfully!")
            return True
        else:
            print(f"⚠️ Outdoor year {year} had some issues during processing")
            return False
    
    def process_indoor_year_data(self, year):
        """
        Process a single year's indoor data
        """
        csv_file_path = f"data/indoor_temp_data/indoor_temperatures_{year}.csv"
        
        if not os.path.exists(csv_file_path):
            print(f"❌ Indoor CSV file not found: {csv_file_path}")
            return False
        
        print(f"🚀 Processing indoor data for year {year}...")
        
        # Step 1: Clear existing indoor data for this year
        self.clear_existing_indoor_data(year)
        
        # Step 2: Upload to Azure SQL Database
        sql_success = self.upload_indoor_csv_to_azure_sql(csv_file_path, year)
        
        # Step 3: Upload to Azure Blob Storage
        blob_success = self.upload_csv_to_blob_storage(csv_file_path, year, "indoor")
        
        if sql_success and blob_success:
            print(f"✅ Indoor year {year} processed successfully!")
            return True
        else:
            print(f"⚠️ Indoor year {year} had some issues during processing")
            return False
    
    def process_all_years(self, years):
        """
        Process multiple years of both outdoor and indoor data
        """
        successful_outdoor_years = 0
        successful_indoor_years = 0
        
        print(f"🚀 Starting data storage process for years: {years}")
        print("=" * 60)
        
        for year in years:
            print(f"\n📅 Processing year {year}:")
            print("-" * 30)
            
            # Process outdoor data
            outdoor_success = self.process_outdoor_year_data(year)
            if outdoor_success:
                successful_outdoor_years += 1
            
            # Process indoor data
            indoor_success = self.process_indoor_year_data(year)
            if indoor_success:
                successful_indoor_years += 1
        
        print("\n" + "=" * 60)
        print("🎉 STORAGE COMPLETED:")
        print(f"✅ Outdoor: {successful_outdoor_years}/{len(years)} years successfully processed")
        print(f"✅ Indoor:  {successful_indoor_years}/{len(years)} years successfully processed")
        print("\n📊 Data stored in:")
        print("- Outdoor: 'OutdoorTempData2020_2025' table")
        print("- Indoor:  'IndoorTempData2020_2025' table (with HVAC levels)")


    def clear_predictions_for_date(self, year, month, day):
        """
        Clear predictions for a specific date
        """
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM TemperaturePredictions WHERE year = ? AND month = ? AND day = ?",
                year, month, day
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"🧹 Cleared predictions for {year}-{month:02d}-{day:02d}")
            return True
            
        except Exception as e:
            print(f"❌ Error clearing predictions: {e}")
            return False

