"""PROPRIETARY — DO NOT DISTRIBUTE — © Acme Corp"""

# examples/demo_app/secret_algorithm.py
#
# This module contains the proprietary churn-risk scoring algorithm.
# It is the intellectual property that PyShield is designed to protect.
#
# The algorithm is a logistic regression (sigmoid) scoring function that
# takes customer attributes and returns a probability between 0.0 and 1.0,
# where 1.0 means extremely high churn risk and 0.0 means very low risk.
#
# The numeric weights below are the "secret" — they were derived from months
# of analysis on historical customer data and represent significant business
# value.  Once the code is obfuscated by PyArmor, these constants will not
# appear as readable text in the binary.
#
# All public functions have full docstrings with Args, Returns, and Raises
# sections so that they are understandable to screen-reader users.

import math  # The standard library math module provides the exp() function.

# --- Magic constants (proprietary weights) ---
# These values are the result of calibrating the model against real customer
# churn data.  Each one encodes a business insight about which customer
# attributes predict churn.

# AGE_WEIGHT: Older customers churn slightly more (positive weight).
AGE_WEIGHT = 0.0234

# INCOME_WEIGHT: Higher-income customers churn less (negative weight).
# The magnitude is small because income varies over a very wide range.
INCOME_WEIGHT = -0.0000891

# TENURE_WEIGHT: Longer-tenured customers churn less (negative weight).
# Customers who have stayed for many months are more likely to keep staying.
TENURE_WEIGHT = -0.1567

# PRODUCT_WEIGHT: Customers with more products churn less (negative weight).
# Multiple product relationships create switching costs and loyalty.
PRODUCT_WEIGHT = -0.4123

# TICKET_WEIGHT: More support tickets strongly predicts churn (positive weight).
# A customer who contacts support frequently is signalling dissatisfaction.
TICKET_WEIGHT = 0.7891

# BIAS_TERM: The intercept of the logistic regression.
# This shifts the overall curve so the base churn rate reflects reality.
BIAS_TERM = 2.4567


def compute_churn_risk(row: dict) -> float:
    """Compute the churn-risk probability for a single customer record.

    Uses a logistic (sigmoid) scoring function with the proprietary weights
    defined above.  The formula is: 1 / (1 + exp(-(BIAS + sum of weight*feature))).

    Args:
        row: A dictionary with the following string keys and numeric values.
             - customer_id: A string identifier (not used in the calculation).
             - age: The customer's age in years (integer or float).
             - income: The customer's annual income in dollars.
             - tenure_months: How many months the customer has been with us.
             - product_count: How many of our products the customer holds.
             - support_tickets: Number of support tickets raised in the last year.

    Returns:
        A float between 0.0 (no churn risk) and 1.0 (certain to churn).
        The value is the output of the sigmoid function applied to the
        weighted sum of features.

    Raises:
        KeyError: If a required column is missing from the row dictionary.
        ValueError: If a column value cannot be converted to a float.
    """

    # Extract each feature from the row dictionary and convert to float.
    # We convert to float so that integer strings like "25" work correctly.
    # A KeyError here means a required column is missing from the input CSV.
    age = float(row["age"])
    income = float(row["income"])
    tenure_months = float(row["tenure_months"])
    product_count = float(row["product_count"])
    support_tickets = float(row["support_tickets"])

    # Compute the linear combination: bias + sum of (weight * feature).
    # This is the "raw score" before the sigmoid transforms it to a probability.
    linear_score = (
        BIAS_TERM
        + AGE_WEIGHT * age
        + INCOME_WEIGHT * income
        + TENURE_WEIGHT * tenure_months
        + PRODUCT_WEIGHT * product_count
        + TICKET_WEIGHT * support_tickets
    )

    # Apply the sigmoid (logistic) function to squash the raw score into [0, 1].
    # 1 / (1 + e^(-z)) is the standard logistic function.
    # A large positive z gives a result close to 1.0 (high churn risk).
    # A large negative z gives a result close to 0.0 (low churn risk).
    churn_probability = 1.0 / (1.0 + math.exp(-linear_score))

    # Return the probability as a float.
    return churn_probability
