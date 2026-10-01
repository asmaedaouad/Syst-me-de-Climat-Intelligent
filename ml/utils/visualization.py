import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime
import os

def validate_temperature_data(year_to_analyze=2024, data_type="outdoor"):
    """
    Perform 5 essential validation checks with seaborn styling
    for both outdoor and indoor temperature data
    """
    
    # Determine file path based on data type
    if data_type == "outdoor":
        file_path = f'data/outdoor_temp_data/hourly_temperatures_{year_to_analyze}.csv'
        temp_column = 'temperature'
        title_suffix = 'Outdoor'
    else:
        file_path = f'data/indoor_temp_data/indoor_temperatures_{year_to_analyze}.csv'
        temp_column = 'indoor_temperature'
        title_suffix = 'Indoor'
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    # Read the data
    df = pd.read_csv(file_path)
    
    # Create datetime column
    df['datetime'] = pd.to_datetime(df['timestamp'])
    
    print(f"🔍 VALIDATING {title_suffix.upper()} TEMPERATURE DATA FOR {year_to_analyze}")
    print("=" * 60)
    
    # Set seaborn style
    sns.set_style("whitegrid")
    sns.set_palette("husl")
    
    # Create a comprehensive figure
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle(f'{title_suffix} Temperature Analysis - {year_to_analyze}', fontsize=16, fontweight='bold')
    
    # ✅ 1. Plot 1 Month of Data (Hourly Curve)
    ax1 = plt.subplot(2, 3, 1)
    plot_one_month_hourly_seaborn(df, ax1, month=7, temp_column=temp_column, title_suffix=title_suffix)
    
    # ✅ 2. Plot the Whole Year (Daily Average Curve)
    ax2 = plt.subplot(2, 3, 2)
    plot_yearly_daily_average_seaborn(df, ax2, temp_column=temp_column, title_suffix=title_suffix)
    
    # ✅ 3. Compare Distributions (Histogram)
    ax3 = plt.subplot(2, 3, 3)
    plot_temperature_distribution_seaborn(df, ax3, temp_column=temp_column, title_suffix=title_suffix)
    
    # ✅ 4. Statistical Checks
    ax4 = plt.subplot(2, 3, 4)
    display_statistical_summary_seaborn(df, ax4, temp_column=temp_column, title_suffix=title_suffix)
    
    # ✅ 5. Seasonal Logic Check
    ax5 = plt.subplot(2, 3, 5)
    plot_seasonal_patterns_seaborn(df, ax5, temp_column=temp_column, title_suffix=title_suffix)
    
    # Bonus: Heatmap
    ax6 = plt.subplot(2, 3, 6)
    plot_temperature_heatmap_seaborn(df, ax6, temp_column=temp_column, title_suffix=title_suffix)
    
    plt.tight_layout()
    plt.show()
    
    # Print validation report
    print_validation_report_seaborn(df, temp_column=temp_column, title_suffix=title_suffix)

def plot_one_month_hourly_seaborn(df, ax, month=7, temp_column='temperature', title_suffix=''):
    """✅ Check 1: Plot 1 month of hourly data with seaborn"""
    month_df = df[df['datetime'].dt.month == month].copy()
    
    # Create a better plot with seaborn
    sns.lineplot(data=month_df, x='datetime', y=temp_column, ax=ax, alpha=0.8, linewidth=1)
    ax.set_title(f'✅ 1. Daily Cycle (Month {month}) - {title_suffix}', fontweight='bold', fontsize=12)
    ax.set_ylabel('Temperature (°C)')
    ax.tick_params(axis='x', rotation=45)
    
    # Add daily swing info
    daily_avg_swing = month_df.groupby(month_df['datetime'].dt.hour)[temp_column].mean()
    swing_range = daily_avg_swing.max() - daily_avg_swing.min()
    
    ax.text(0.02, 0.98, f'Daily Swing: {swing_range:.1f}°C', 
            transform=ax.transAxes, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

def plot_yearly_daily_average_seaborn(df, ax, temp_column='temperature', title_suffix=''):
    """✅ Check 2: Plot yearly daily averages with seaborn"""
    daily_avg = df.groupby(df['datetime'].dt.date)[temp_column].mean().reset_index()
    daily_avg['date'] = pd.to_datetime(daily_avg['datetime'])
    
    sns.lineplot(data=daily_avg, x='date', y=temp_column, ax=ax, alpha=0.8, linewidth=1)
    ax.set_title(f'✅ 2. Seasonal Cycle (Daily Averages) - {title_suffix}', fontweight='bold', fontsize=12)
    ax.set_ylabel('Temperature (°C)')
    ax.tick_params(axis='x', rotation=45)

def plot_temperature_distribution_seaborn(df, ax, temp_column='temperature', title_suffix=''):
    """✅ Check 3: Temperature distribution with seaborn"""
    sns.histplot(data=df, x=temp_column, bins=30, ax=ax, kde=True, alpha=0.7)
    ax.set_title(f'✅ 3. Temperature Distribution - {title_suffix}', fontweight='bold', fontsize=12)
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Frequency')
    
    # Add mean line
    mean_temp = df[temp_column].mean()
    ax.axvline(mean_temp, color='red', linestyle='--', label=f'Mean: {mean_temp:.1f}°C')
    ax.legend()

def display_statistical_summary_seaborn(df, ax, temp_column='temperature', title_suffix=''):
    """✅ Check 4: Statistical summary with seaborn style"""
    temps = df[temp_column]
    
    stats = {
        'Minimum': f"{temps.min():.1f}°C",
        'Maximum': f"{temps.max():.1f}°C", 
        'Mean': f"{temps.mean():.1f}°C",
        'Std Dev': f"{temps.std():.1f}°C",
        '25th %ile': f"{temps.quantile(0.25):.1f}°C",
        '75th %ile': f"{temps.quantile(0.75):.1f}°C"
    }
    
    # Clear axis and display text with nice styling
    ax.axis('off')
    ax.set_title(f'✅ 4. Statistical Summary - {title_suffix}', fontweight='bold', fontsize=12)
    
    # Create a nice background
    ax.set_facecolor('#f8f9fa')
    
    y_pos = 0.9
    for stat, value in stats.items():
        ax.text(0.1, y_pos, f"{stat:>10}: {value}", transform=ax.transAxes,
                fontfamily='monospace', fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray'))
        y_pos -= 0.12

def plot_seasonal_patterns_seaborn(df, ax, temp_column='temperature', title_suffix=''):
    """✅ Check 5: Seasonal logic verification with seaborn"""
    monthly_stats = df.groupby(df['datetime'].dt.month).agg({
        temp_column: ['mean', 'min', 'max']
    }).round(1)
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Use seaborn lineplot with confidence interval
    month_data = df.copy()
    month_data['month'] = month_data['datetime'].dt.month
    month_data['month_name'] = month_data['month'].apply(lambda x: months[x-1])
    
    sns.lineplot(data=month_data, x='month_name', y=temp_column, ax=ax, 
                 errorbar='sd', marker='o', linewidth=2.5)
    ax.set_title(f'✅ 5. Seasonal Pattern Check - {title_suffix}', fontweight='bold', fontsize=12)
    ax.set_ylabel('Average Temperature (°C)')
    ax.tick_params(axis='x', rotation=45)

def plot_temperature_heatmap_seaborn(df, ax, temp_column='temperature', title_suffix=''):
    """Bonus: Temperature heatmap with seaborn"""
    # Create day-of-year and hour columns
    df_heatmap = df.copy()
    df_heatmap['day_of_year'] = df_heatmap['datetime'].dt.dayofyear
    df_heatmap['hour'] = df_heatmap['datetime'].dt.hour
    
    # Pivot for heatmap (sample every 5 days to avoid overcrowding)
    heatmap_data = df_heatmap[df_heatmap['day_of_year'] % 5 == 0].pivot_table(
        index='day_of_year', columns='hour', values=temp_column, aggfunc='mean'
    )
    
    sns.heatmap(heatmap_data, ax=ax, cmap='RdYlBu_r', cbar_kws={'label': 'Temperature (°C)'})
    ax.set_title(f'📊 Temperature Heatmap (Day vs Hour) - {title_suffix}', fontweight='bold', fontsize=12)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Day of Year')

def print_validation_report_seaborn(df, temp_column='temperature', title_suffix=''):
    """Print comprehensive validation report"""
    print(f"\n📋 {title_suffix.upper()} VALIDATION REPORT")
    print("=" * 50)
    
    # Basic stats
    temps = df[temp_column]
    print(f"Dataset Size: {len(df):,} hourly records")
    print(f"Date Range: {df['datetime'].min().date()} to {df['datetime'].max().date()}")
    print(f"Temperature Range: {temps.min():.1f}°C to {temps.max():.1f}°C")
    print(f"Overall Average: {temps.mean():.1f}°C")
    
    # Seasonal validation
    monthly_means = df.groupby(df['datetime'].dt.month)[temp_column].mean()
    summer_avg = monthly_means.loc[[6,7,8]].mean()
    winter_avg = monthly_means.loc[[12,1,2]].mean()
    
    print(f"\n🌡️  SEASONAL VALIDATION:")
    print(f"Summer (Jun-Aug) Average: {summer_avg:.1f}°C")
    print(f"Winter (Dec-Feb) Average: {winter_avg:.1f}°C")
    print(f"Seasonal Difference: {summer_avg - winter_avg:.1f}°C")
    
    # Daily pattern validation
    hourly_means = df.groupby(df['datetime'].dt.hour)[temp_column].mean()
    daily_swing = hourly_means.max() - hourly_means.min()
    warmest_hour = hourly_means.idxmax()
    
    print(f"\n🕒 DAILY PATTERN VALIDATION:")
    print(f"Daily Temperature Swing: {daily_swing:.1f}°C")
    print(f"Warmest Hour of Day: {warmest_hour}:00")
    print(f"Coolest Hour of Day: {hourly_means.idxmin()}:00")
    
    # Final assessment
    print(f"\n✅ VALIDATION ASSESSMENT:")
    if (summer_avg > winter_avg and 
        daily_swing > 5 and 
        warmest_hour in [13, 14, 15] and
        temps.min() >= 5 and temps.max() <= 40):
        print(f"🎉 {title_suffix.upper()} DATA PASSES ALL CHECKS - READY FOR ML!")
    else:
        print(f"⚠️  Some checks need review - see graphs above")

def compare_outdoor_indoor(year_to_analyze=2024):
    """
    Compare outdoor and indoor temperature data for the same year
    """
    try:
        # Read both datasets
        outdoor_df = pd.read_csv(f'data/outdoor_temp_data/hourly_temperatures_{year_to_analyze}.csv')
        indoor_df = pd.read_csv(f'data/indoor_temp_data/indoor_temperatures_{year_to_analyze}.csv')
        
        # Create datetime columns
        outdoor_df['datetime'] = pd.to_datetime(outdoor_df['timestamp'])
        indoor_df['datetime'] = pd.to_datetime(indoor_df['timestamp'])
        
        print(f"Outdoor columns: {outdoor_df.columns.tolist()}")
        print(f"Indoor columns: {indoor_df.columns.tolist()}")
        
        # Merge datasets - use correct column names
        merged_df = pd.merge(outdoor_df, indoor_df, on=['datetime', 'year', 'month', 'day', 'hour'], 
                           suffixes=('_outdoor', '_indoor'))
        
        print(f"Merged columns: {merged_df.columns.tolist()}")
        
        print(f"🔍 COMPARING OUTDOOR vs INDOOR TEMPERATURES - {year_to_analyze}")
        print("=" * 60)
        
        # Create comparison plots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Outdoor vs Indoor Temperature Comparison - {year_to_analyze}', fontsize=16, fontweight='bold')
        
        # Scatter plot - use correct column names
        axes[0,0].scatter(merged_df['temperature'], merged_df['indoor_temperature'], alpha=0.5)
        axes[0,0].plot([merged_df['temperature'].min(), merged_df['temperature'].max()], 
                      [merged_df['temperature'].min(), merged_df['temperature'].max()], 
                      'r--', alpha=0.8)
        axes[0,0].set_xlabel('Outdoor Temperature (°C)')
        axes[0,0].set_ylabel('Indoor Temperature (°C)')
        axes[0,0].set_title('Outdoor vs Indoor Correlation')
        axes[0,0].grid(True, alpha=0.3)
        
        # Distribution comparison
        sns.histplot(merged_df['temperature'], ax=axes[0,1], label='Outdoor', alpha=0.7, kde=True)
        sns.histplot(merged_df['indoor_temperature'], ax=axes[0,1], label='Indoor', alpha=0.7, kde=True)
        axes[0,1].set_xlabel('Temperature (°C)')
        axes[0,1].set_ylabel('Frequency')
        axes[0,1].set_title('Temperature Distribution Comparison')
        axes[0,1].legend()
        
        # Time series sample (1 week)
        sample_df = merged_df.head(24*7)  # First week
        axes[1,0].plot(sample_df['datetime'], sample_df['temperature'], label='Outdoor', alpha=0.8)
        axes[1,0].plot(sample_df['datetime'], sample_df['indoor_temperature'], label='Indoor', alpha=0.8)
        axes[1,0].set_xlabel('Date')
        axes[1,0].set_ylabel('Temperature (°C)')
        axes[1,0].set_title('One Week Sample')
        axes[1,0].legend()
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # Temperature difference
        merged_df['temp_difference'] = merged_df['indoor_temperature'] - merged_df['temperature']
        axes[1,1].hist(merged_df['temp_difference'], bins=30, alpha=0.7, edgecolor='black')
        axes[1,1].axvline(merged_df['temp_difference'].mean(), color='red', linestyle='--', 
                         label=f'Mean: {merged_df["temp_difference"].mean():.2f}°C')
        axes[1,1].set_xlabel('Indoor - Outdoor Temperature Difference (°C)')
        axes[1,1].set_ylabel('Frequency')
        axes[1,1].set_title('Temperature Difference Distribution')
        axes[1,1].legend()
        
        plt.tight_layout()
        plt.show()
        
        # Print comparison statistics
        print(f"\n📊 COMPARISON STATISTICS:")
        print(f"Outdoor Mean: {merged_df['temperature'].mean():.2f}°C")
        print(f"Indoor Mean: {merged_df['indoor_temperature'].mean():.2f}°C")
        print(f"Average Difference: {merged_df['temp_difference'].mean():.2f}°C")
        print(f"Correlation: {merged_df['temperature'].corr(merged_df['indoor_temperature']):.3f}")
        
    except FileNotFoundError as e:
        print(f"❌ Could not find data files for {year_to_analyze}: {e}")
    except Exception as e:
        print(f"❌ Error comparing outdoor vs indoor: {e}")
        print("Debug info:")
        print(f"Outdoor file: data/outdoor_temp_data/hourly_temperatures_{year_to_analyze}.csv")
        print(f"Indoor file: data/indoor_temp_data/indoor_temperatures_{year_to_analyze}.csv")

# Run validation for all years
if __name__ == "__main__":
    years_to_validate = [2020, 2021, 2022, 2023, 2024, 2025]
    
    print("🌡️ TEMPERATURE DATA VISUALIZATION AND VALIDATION")
    print("=" * 60)
    
    # Validate outdoor data
    for year in years_to_validate:
        try:
            validate_temperature_data(year, "outdoor")
            print("\n" + "="*60 + "\n")
        except Exception as e:
            print(f"❌ Could not validate outdoor {year}: {e}")
            print("\n" + "="*60 + "\n")
    
    # Validate indoor data
    for year in years_to_validate:
        try:
            validate_temperature_data(year, "indoor")
            print("\n" + "="*60 + "\n")
        except Exception as e:
            print(f"❌ Could not validate indoor {year}: {e}")
            print("\n" + "="*60 + "\n")
    
    # Compare outdoor vs indoor for latest year
    try:
        compare_outdoor_indoor(2024)
    except Exception as e:
        print(f"❌ Could not compare outdoor vs indoor: {e}")