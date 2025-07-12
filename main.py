from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
from io import BytesIO
import numpy as np
import os

app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(upload: UploadFile):
    ext = os.path.splitext(upload.filename)[-1].lower()
    if ext == ".csv":
        return pd.read_csv(BytesIO(upload.file.read()))
    elif ext in [".xlsx", ".xls"]:
        return pd.read_excel(BytesIO(upload.file.read()))
    else:
        raise ValueError("Unsupported file format")

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...),
):
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    # Clean and standardize
    for df in [weekly_df, monthly_df]:
        df["Item Name"] = df["Item Name"].astype(str).str.upper().str.strip()
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)

    supplier_df["Item Name"] = supplier_df["Item Name"].astype(str).str.upper().str.strip()

    # Calculate daily averages
    weekly_avg = weekly_df.groupby("Item Name")["Quantity"].sum() / 7
    monthly_avg = monthly_df.groupby("Item Name")["Quantity"].sum() / 30

    par_stock = pd.concat([weekly_avg, monthly_avg], axis=1)
    par_stock.columns = ["Weekly Avg", "Monthly Avg"]
    par_stock["Suggested Par"] = par_stock.max(axis=1)

    # Match items from supplier list
    result = []

    for _, row in par_stock.reset_index().iterrows():
        item_name = row["Item Name"]
        suggested_par = row["Suggested Par"]

        # Try to find matching item in supplier file
        match = supplier_df[supplier_df["Item Name"].str.upper().str.strip() == item_name]
        if match.empty:
            # Try partial match
            match = supplier_df[supplier_df["Item Name"].str.contains(item_name[:8], na=False)]

        if not match.empty:
            supplier_row = match.iloc[0]
            item_code = supplier_row.get("Item Code", "")
            unit = supplier_row.get("Unit", "")
            supplier_name = detect_supplier_name(supplier_file.filename)
        else:
            item_code = ""
            unit = ""
            supplier_name = ""

        result.append({
            "Item Name": item_name,
            "Item Code": item_code,
            "Unit": unit,
            "Suggested Par": round(suggested_par, 2),
            "Stock in Hand": 0,
            "Expected Delivery": 0,
            "Final Stock Needed": 0,
            "Supplier": supplier_name
        })

    return result

def detect_supplier_name(filename: str):
    name = filename.lower()
    if "barakat" in name:
        return "Barakat"
    elif "ofi" in name:
        return "OFI"
    elif "ahlia" in name:
        return "Al Ahlia"
    elif "emirates" in name:
        return "Emirates"
    elif "harvey" in name:
        return "Harvey"
    else:
        return "Unknown"