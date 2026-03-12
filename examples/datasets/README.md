# Example Datasets

This directory contains example datasets for testing and demonstrating AnyPlot's privacy-preserving visualization capabilities.

## 📊 Available Datasets

### 1. Sales Data (`sales_data.csv`)

**Use Case:** Business analytics, quarterly reporting  
**Privacy Level:** Medium (contains revenue information)  
**Rows:** 20  
**Columns:** 6

**Schema:**
- `date` (string) - Transaction date
- `region` (string) - Geographic region (North, South, East, West)
- `product` (string) - Product name (Widget A, B, C)
- `revenue` (float) - Revenue in dollars
- `units_sold` (integer) - Number of units sold
- `sales_rep` (string) - Sales representative name

**Example Queries:**
```sql
-- Total revenue by region
SELECT region, SUM(revenue) as total_revenue 
FROM sales 
GROUP BY region 
ORDER BY total_revenue DESC;

-- Monthly sales trend
SELECT strftime('%Y-%m', date) as month, SUM(revenue) as monthly_revenue
FROM sales
GROUP BY month;
```

**Visualization Ideas:**
- "Create a bar chart showing total revenue by region"
- "Show monthly sales trend over time"
- "Compare product performance across regions"

---

### 2. Survey Results (`survey_results.csv`)

**Use Case:** HR analytics, employee satisfaction  
**Privacy Level:** High (contains sensitive employee data)  
**Rows:** 20  
**Columns:** 6

**Schema:**
- `employee_id` (string) - Anonymous employee ID
- `department` (string) - Department name
- `satisfaction_score` (integer) - Satisfaction rating (1-10)
- `years_employed` (integer) - Years with company
- `remote_work_days` (integer) - Remote work days per week
- `salary_band` (string) - Salary range (anonymized)

**Example Queries:**
```sql
-- Average satisfaction by department
SELECT department, AVG(satisfaction_score) as avg_satisfaction
FROM survey
GROUP BY department;

-- Correlation between remote work and satisfaction
SELECT remote_work_days, AVG(satisfaction_score) as avg_satisfaction
FROM survey
GROUP BY remote_work_days;
```

**Visualization Ideas:**
- "Show average satisfaction score by department"
- "Create a scatter plot of years employed vs satisfaction"
- "Compare satisfaction between high and low remote work"

**Privacy Notes:**
- This dataset demonstrates differential privacy with sensitive employee data
- Column names are masked (e.g., `satisfaction_score` → `col_a8f3`)
- Statistics are noisy to protect individual privacy

---

### 3. IoT Sensors (`iot_sensors.csv`)

**Use Case:** Time series analysis, sensor monitoring  
**Privacy Level:** Low (technical data, not personal)  
**Rows:** 20  
**Columns:** 6

**Schema:**
- `timestamp` (string) - ISO 8601 timestamp
- `sensor_id` (string) - Sensor identifier
- `temperature` (float) - Temperature in Celsius
- `humidity` (float) - Humidity percentage
- `pressure` (float) - Atmospheric pressure in hPa
- `location` (string) - Physical location

**Example Queries:**
```sql
-- Average temperature by location
SELECT location, AVG(temperature) as avg_temp
FROM sensors
GROUP BY location;

-- Temperature trend over time for Building A
SELECT timestamp, temperature
FROM sensors
WHERE location = 'Building A'
ORDER BY timestamp;
```

**Visualization Ideas:**
- "Plot temperature trends over time for each building"
- "Create a scatter plot of temperature vs humidity"
- "Show average conditions by location"

---

### 4. Customer Churn (`customer_churn.csv`)

**Use Case:** Customer analytics, churn prediction  
**Privacy Level:** Medium (contains customer behavior data)  
**Rows:** 20  
**Columns:** 6

**Schema:**
- `customer_id` (string) - Anonymous customer ID
- `tenure_months` (integer) - Months as customer
- `monthly_charges` (float) - Monthly subscription cost
- `total_charges` (float) - Total revenue from customer
- `contract_type` (string) - Contract type (Month-to-month, One year, Two year)
- `churn` (string) - Whether customer churned (Yes/No)

**Example Queries:**
```sql
-- Churn rate by contract type
SELECT contract_type, 
       SUM(CASE WHEN churn = 'Yes' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as churn_rate
FROM churn
GROUP BY contract_type;

-- Average tenure for churned vs retained
SELECT churn, AVG(tenure_months) as avg_tenure
FROM churn
GROUP BY churn;
```

**Visualization Ideas:**
- "Compare churn rates by contract type"
- "Show relationship between tenure and monthly charges"
- "Visualize total charges distribution for churned customers"

---

### 5. Medical Records (`medical_records.csv`)

**Use Case:** Healthcare analytics, patient monitoring  
**Privacy Level:** Very High (protected health information)  
**Rows:** 20  
**Columns:** 7

**Schema:**
- `patient_id` (string) - Anonymous patient ID
- `age` (integer) - Patient age
- `blood_pressure_systolic` (integer) - Systolic BP (mmHg)
- `blood_pressure_diastolic` (integer) - Diastolic BP (mmHg)
- `cholesterol` (integer) - Cholesterol level (mg/dL)
- `bmi` (float) - Body Mass Index
- `diagnosis` (string) - Medical diagnosis

**Example Queries:**
```sql
-- Average BP by diagnosis
SELECT diagnosis, 
       AVG(blood_pressure_systolic) as avg_systolic,
       AVG(blood_pressure_diastolic) as avg_diastolic
FROM medical
GROUP BY diagnosis;

-- Age distribution by diagnosis
SELECT diagnosis, AVG(age) as avg_age, COUNT(*) as patient_count
FROM medical
GROUP BY diagnosis;
```

**Visualization Ideas:**
- "Show blood pressure distribution by diagnosis"
- "Create a scatter plot of BMI vs cholesterol"
- "Compare age distributions across diagnoses"

**Privacy Notes:**
- This dataset requires the highest privacy protection (HIPAA-like)
- Use lower epsilon values (0.5 or less) for stronger privacy
- All patient identifiers are anonymized
- Differential privacy is critical for this use case

---

## 🔒 Privacy Considerations

### Dataset Privacy Levels

| Dataset | Privacy Level | Recommended Epsilon | Notes |
|---------|---------------|---------------------|-------|
| Sales Data | Medium | 1.0 | Revenue data is sensitive but not personal |
| Survey Results | High | 0.5 | Employee data requires strong privacy |
| IoT Sensors | Low | 2.0 | Technical data, no personal information |
| Customer Churn | Medium | 1.0 | Customer behavior data |
| Medical Records | Very High | 0.1-0.5 | Protected health information |

### Using These Datasets

**In Development:**
```bash
# Quick test with default settings
anyplot test-viz examples/datasets/sales_data.csv

# Check privacy budget
anyplot check-privacy examples/datasets/medical_records.csv --epsilon=0.5
```

**In Production:**
- Always review privacy budget before deployment
- Use appropriate epsilon values for data sensitivity
- Audit all visualizations for privacy leaks
- Document privacy parameters in configuration

---

## 🚀 Quick Start Examples

### Example 1: Basic Visualization
```bash
# Load sales data and create a visualization
anyplot test-viz examples/datasets/sales_data.csv \
  --prompt "Create a bar chart of revenue by region"
```

### Example 2: Custom Privacy Settings
```bash
# Use stricter privacy for medical data
anyplot test-viz examples/datasets/medical_records.csv \
  --epsilon 0.5 \
  --prompt "Show average blood pressure by diagnosis"
```

### Example 3: Interactive Session
```bash
# Start dev server with example data pre-loaded
anyplot dev-server --load examples/datasets/survey_results.csv
```

---

## 📝 Adding Your Own Datasets

To add custom datasets:

1. **Format:** Save as CSV with headers
2. **Size:** Keep reasonable for testing (<10MB)
3. **Privacy:** Document sensitivity level
4. **Documentation:** Add to this README with:
   - Schema description
   - Example queries
   - Visualization ideas
   - Privacy considerations

**Template:**
```markdown
### N. Dataset Name (`filename.csv`)

**Use Case:** Brief description
**Privacy Level:** Low/Medium/High/Very High
**Rows:** X
**Columns:** Y

**Schema:**
- `column1` (type) - Description
...

**Example Queries:**
```sql
-- Query example
```

**Visualization Ideas:**
- "Suggestion 1"
- "Suggestion 2"

**Privacy Notes:**
- Special considerations
```

---

## 🧪 Testing with Example Datasets

All example datasets are automatically tested in the CI pipeline:

```bash
# Run unit tests with example data
pytest tests/test_examples.py

# Run full E2E test with all datasets
pytest tests/test_e2e_examples.py
```

---

## 📚 Additional Resources

- [AnyPlot Documentation](../../README.md)
- [Privacy Guide](../../docs/PRIVACY.md)
- [API Reference](../../docs/API.md)
- [Contributing Guide](../../docs/CONTRIBUTING.md)

---

**Last Updated:** March 12, 2026
