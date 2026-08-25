"""Raw data loading with memory-efficient dtypes."""

import numpy as np
import pandas as pd

from . import config


def load_application():
    """
    The main application table: one row per loan application.
    307,511 rows x 122 columns, TARGET = 1 if the client had payment
    difficulties (late payment > X days on at least one installment).
    """
    df = pd.read_csv(config.DATA_DIR / "application_train.csv")
    # halve memory: float64 -> float32 for the wide float blocks
    for col in df.select_dtypes("float64").columns:
        df[col] = df[col].astype("float32")
    return df


def load_bureau():
    """
    Credit-bureau records: one row per PREVIOUS credit reported by other
    institutions. 1.7M rows; joins to the application on SK_ID_CURR.
    This is the "Character" evidence in Five-Cs terms - repayment history
    with other lenders.
    """
    df = pd.read_csv(config.DATA_DIR / "bureau.csv")
    for col in df.select_dtypes("float64").columns:
        df[col] = df[col].astype("float32")
    return df


def stratified_split(df, target="TARGET", val_frac=config.VAL_FRACTION,
                     test_frac=config.TEST_FRACTION, seed=config.SEED):
    """
    Stratified train/validation/test split (the dataset has no dates, so a
    temporal split is impossible - see config.py). Returns three DataFrames.
    """
    from sklearn.model_selection import train_test_split

    trainval, test = train_test_split(
        df, test_size=test_frac, stratify=df[target], random_state=seed)
    train, val = train_test_split(
        trainval, test_size=val_frac / (1 - test_frac),
        stratify=trainval[target], random_state=seed)
    return (train.reset_index(drop=True), val.reset_index(drop=True),
            test.reset_index(drop=True))
