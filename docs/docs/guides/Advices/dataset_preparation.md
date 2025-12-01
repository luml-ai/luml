---
sidebar_position: 1
---

# Dataset Preparation

## Importance of Data Preparation in Machine Learning
Data preparation is a crucial step in machine learning because a model can only learn from the data it receives, and its quality directly affects prediction accuracy. Dirty data, such as missing values, duplicates, or incorrect entries, can lead the model to learn wrong patterns. Machine learning algorithms work only with numerical inputs, so text and date features need to be converted into numbers, for example through encoding or extracting year, month, and day from dates.
Different feature scales can distort learning, and outliers can heavily influence averages and variances, causing the model to adapt incorrectly. Imbalanced target variables may lead the model to favor the majority class, which can be addressed through class balancing or weighting. Highly correlated or redundant features can cause overfitting or instability, so they should be detected and handled. Proper splitting into training, validation, and test sets prevents data leakage and ensures realistic evaluation, especially for time-series data.
Careful data preparation makes models more stable, interpretable, and better at generalizing to new data, resulting in more reliable and accurate predictions.

## Most common steps in Data Preparation
#### 1. Handling missing data
Handling missing data is an essential first step in data preparation. Missing values can be removed, filled with statistical measures such as the mean, median, or mode, or replaced with a separate category for categorical features, depending on the nature of the data.
#### 2. Handling outliers
Handling outliers is also important because extreme values can distort statistical measures and bias the model. Outliers can be addressed by trimming, winsorization, or applying transformations such as logarithms to reduce skewness. In some cases, dropping all anomalous data points may be necessary if they are clearly invalid or erroneous.
#### 3. Drop all anomalous data
Handling anomalous data is closely related to managing outliers, but it’s a slightly broader concept. Anomalous data refers to observations that deviate significantly from expected patterns, which may include errors, corrupted entries, or rare events that are not representative of the general population.
These anomalies can negatively affect model training by introducing noise or bias. Common approaches to handling anomal data include:
- Detection: Identify anomalies using statistical methods (e.g., values beyond 3 standard deviations), clustering, or specialized anomaly detection algorithms.
- Removal: If anomalies are clearly invalid (e.g., negative ages, impossible dates), it’s often safest to remove them.
- Correction or Imputation: Sometimes anomalies can be corrected based on domain knowledge or replaced with reasonable estimates.
- Separate Treatment: In certain cases, anomalies may carry important information (fraud detection, rare events) and should be treated as a separate class or feature rather than removed.

Incorporating anomaly handling into data preparation ensures the model is not misled by unusual or erroneous points, improving stability, generalization, and overall predictive performance.

#### 4. Checking data type for every feature
Checking the data type for every feature ensures that numeric, categorical, and date values are correctly represented. Numeric features should be stored as numbers, dates as datetime objects, and categorical features as strings or categories.
one-hot encoding for categorical feature
Categorical features are often converted using one-hot encoding, which transforms each category into a separate binary column. This allows machine learning algorithms to process categorical information numerically without assuming an ordinal relationship.

#### 5. Normalize numerical data
Numerical data should be normalized or standardized to ensure that features are on a comparable scale, which is particularly important for distance-based models or gradient-based optimization. Standardization (subtracting the mean and dividing by the standard deviation) or Min-Max scaling are commonly used methods.

#### 6. Feature engineering
Feature engineering involves creating new informative features from existing ones, such as extracting day, month, and weekday from dates, generating ratios or differences between variables, or aggregating data to capture higher-level patterns. This step can significantly improve model performance by providing additional signals that the model can learn from.
Overall, careful and systematic data preparation improves model stability, interpretability, and predictive performance. By addressing missing values, outliers, data types, encoding, scaling, and feature creation, we ensure the model learns meaningful patterns, generalizes better to new data, and avoids common pitfalls such as overfitting or bias. Properly prepared data is the fo2undation for reliable and accurate machine learning outcomes.

## Code example of data preparation pipeline

``` python
import numpy as np
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Example dataset
data = {
    'age': [25, 30, np.nan, 22, 1000, 28],
    'salary': [50000, 60000, 55000, np.nan, 70000, 65000],
    'department': ['HR', 'IT', 'IT', 'HR', 'Finance', 'IT'],
    'join_date': ['2020-01-10', '2019-06-23', '2021-03-15', '2020-11-05', '2020-02-30', '2019-12-12']
}

df = pd.DataFrame(data)

# 1. Handling missing data
df['age'].fillna(df['age'].median(), inplace=True)
df['salary'].fillna(df['salary'].mean(), inplace=True)

# 2. Handling outliers (example using capping/winsorization)
age_upper_limit = df['age'].quantile(0.95)
df['age'] = np.where(df['age'] > age_upper_limit, age_upper_limit, df['age'])

# 3. Dropping anomalous data (e.g., impossible dates)
df['join_date'] = pd.to_datetime(df['join_date'], errors='coerce')  # invalid dates become NaT
df.dropna(subset=['join_date'], inplace=True)

# 4. Checking and correcting data types
df['age'] = df['age'].astype(int)
df['salary'] = df['salary'].astype(float)
df['department'] = df['department'].astype(str)

# 5. One-hot encoding for categorical features
encoder = OneHotEncoder(sparse=False, drop='first')
dept_encoded = encoder.fit_transform(df[['department']])
dept_df = pd.DataFrame(dept_encoded, columns=encoder.get_feature_names_out(['department']))
df = pd.concat([df.drop('department', axis=1), dept_df], axis=1)

# 6. Normalize numerical data
scaler = StandardScaler()
df[['age', 'salary']] = scaler.fit_transform(df[['age', 'salary']])

# 7. Feature engineering (extracting info from dates)
df['join_year'] = df['join_date'].dt.year
df['join_month'] = df['join_date'].dt.month
df['join_weekday'] = df['join_date'].dt.weekday
df.drop('join_date', axis=1, inplace=True)

print(df)



