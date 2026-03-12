#!/usr/bin/env python3
"""
Generate test datasets for development and testing

Usage:
    python scripts/seed-data.py --rows=1000 --output=test_data.csv
    python scripts/seed-data.py --type=timeseries --output=sensor_data.csv
"""

import argparse
import random
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


def generate_sales_data(rows: int) -> pd.DataFrame:
    """Generate realistic sales data"""
    regions = ["North", "South", "East", "West"]
    products = ["Widget A", "Widget B", "Widget C", "Gadget X", "Gadget Y"]
    reps = ["Alice Chen", "Bob Martinez", "Carol Singh", "David Kim", "Eve Lopez"]
    
    start_date = datetime(2025, 1, 1)
    
    data = []
    for i in range(rows):
        date = start_date + timedelta(days=random.randint(0, 365))
        region = random.choice(regions)
        product = random.choice(products)
        units = random.randint(50, 500)
        price = random.uniform(30, 100)
        revenue = units * price
        rep = random.choice(reps)
        
        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "region": region,
            "product": product,
            "revenue": round(revenue, 2),
            "units_sold": units,
            "sales_rep": rep
        })
    
    return pd.DataFrame(data)


def generate_timeseries_data(rows: int) -> pd.DataFrame:
    """Generate time series sensor data"""
    sensors = ["S001", "S002", "S003", "S004"]
    locations = ["Building A", "Building B", "Building C", "Building D"]
    
    start_time = datetime(2025, 3, 12, 8, 0, 0)
    
    data = []
    for i in range(rows):
        timestamp = start_time + timedelta(minutes=i * 15)
        sensor = sensors[i % len(sensors)]
        location = locations[i % len(locations)]
        
        # Simulate realistic sensor readings with some drift
        base_temp = 22.0 + (i % 100) * 0.05
        temperature = base_temp + random.uniform(-2, 2)
        
        base_humidity = 45.0 + (i % 100) * 0.1
        humidity = base_humidity + random.uniform(-5, 5)
        
        pressure = 1013.0 + random.uniform(-2, 2)
        
        data.append({
            "timestamp": timestamp.isoformat(),
            "sensor_id": sensor,
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 1),
            "location": location
        })
    
    return pd.DataFrame(data)


def generate_survey_data(rows: int) -> pd.DataFrame:
    """Generate employee survey data"""
    departments = ["Engineering", "Marketing", "Sales", "HR", "Finance"]
    salary_bands = ["50000-75000", "75000-100000", "100000-150000", "150000-200000"]
    
    data = []
    for i in range(rows):
        data.append({
            "employee_id": f"E{i+1:03d}",
            "department": random.choice(departments),
            "satisfaction_score": random.randint(5, 10),
            "years_employed": random.randint(1, 10),
            "remote_work_days": random.randint(0, 5),
            "salary_band": random.choice(salary_bands)
        })
    
    return pd.DataFrame(data)


def generate_churn_data(rows: int) -> pd.DataFrame:
    """Generate customer churn data"""
    contract_types = ["Month-to-month", "One year", "Two year"]
    
    data = []
    for i in range(rows):
        tenure = random.randint(1, 72)
        monthly_charges = random.uniform(40, 110)
        total_charges = monthly_charges * tenure
        contract = random.choice(contract_types)
        
        # Churn probability based on tenure and contract
        churn_prob = 0.3 if contract == "Month-to-month" else 0.1
        churn_prob *= (1.0 - tenure / 100)  # Lower for longer tenure
        churn = "Yes" if random.random() < churn_prob else "No"
        
        data.append({
            "customer_id": f"C{i+1:03d}",
            "tenure_months": tenure,
            "monthly_charges": round(monthly_charges, 2),
            "total_charges": round(total_charges, 2),
            "contract_type": contract,
            "churn": churn
        })
    
    return pd.DataFrame(data)


def generate_medical_data(rows: int) -> pd.DataFrame:
    """Generate anonymized medical records"""
    diagnoses = ["Healthy", "Pre-hypertension", "Hypertension", "Diabetes"]
    
    data = []
    for i in range(rows):
        age = random.randint(25, 80)
        
        # Realistic correlations
        if age < 40:
            diagnosis = random.choice(["Healthy", "Pre-hypertension"])
            bp_systolic = random.randint(110, 130)
            bmi = random.uniform(20, 27)
        elif age < 60:
            diagnosis = random.choice(["Healthy", "Pre-hypertension", "Hypertension"])
            bp_systolic = random.randint(115, 145)
            bmi = random.uniform(22, 29)
        else:
            diagnosis = random.choice(["Pre-hypertension", "Hypertension", "Diabetes"])
            bp_systolic = random.randint(120, 160)
            bmi = random.uniform(24, 33)
        
        bp_diastolic = int(bp_systolic * 0.6) + random.randint(-5, 5)
        cholesterol = random.randint(150, 280)
        
        data.append({
            "patient_id": f"P{i+1:03d}",
            "age": age,
            "blood_pressure_systolic": bp_systolic,
            "blood_pressure_diastolic": bp_diastolic,
            "cholesterol": cholesterol,
            "bmi": round(bmi, 1),
            "diagnosis": diagnosis
        })
    
    return pd.DataFrame(data)


def main():
    parser = argparse.ArgumentParser(description="Generate test datasets")
    parser.add_argument("--rows", type=int, default=100, help="Number of rows to generate")
    parser.add_argument("--type", choices=["sales", "timeseries", "survey", "churn", "medical"],
                       default="sales", help="Dataset type")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    if args.seed:
        random.seed(args.seed)
    
    # Generate data based on type
    generators = {
        "sales": generate_sales_data,
        "timeseries": generate_timeseries_data,
        "survey": generate_survey_data,
        "churn": generate_churn_data,
        "medical": generate_medical_data
    }
    
    print(f"Generating {args.type} dataset with {args.rows} rows...")
    df = generators[args.type](args.rows)
    
    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"✓ Saved to: {output_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"\nFirst few rows:")
    print(df.head())


if __name__ == "__main__":
    main()
