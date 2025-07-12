from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import List
import io

app = FastAPI()

# CORS setup for Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://preeminent-choux-a8ea17.netlify.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper: Read any Excel or CSV file
def read_file(file: UploadFile):
    contents = file.file.read()
    if file.filename.endswith(".csv"):
        return pd.read_csv(io.BytesIO(contents))
    else:
        return pd.read_excel(io.BytesIO(contents))

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    try:
        # Load all files
        weekly_df = read_file(weekly_file)
        monthly_df = read_file(monthly_file)
        supplier_df = read_file(supplier_file)

        # Normalize column names
        weekly_df.columns = [str(col).strip().upper() for col in weekly_df.columns]
        monthly_df.columns = [str(col).strip().upper() for col in monthly_df.columns]
        supplier_df.columns = [str(col).strip().upper() for col in supplier_df.columns]

        # Prepare base data
        item_names = set(weekly_df["ITEM NAME"].dropna().unique()).union(set(monthly_df["ITEM NAME"].dropna().unique()))
        result = []

        for item in item_names:
            # Handle case-insensitive match
            item_str = str(item).strip().upper()
            weekly_row = weekly_df[weekly_df["ITEM NAME"].str.upper().str.strip() == item_str]
            monthly_row = monthly_df[monthly_df["ITEM NAME"].str.upper().str.strip() == item_str]

            weekly_avg = weekly_row["QUANTITY"].sum() / 7 if not weekly_row.empty else 0
            monthly_avg = monthly_row["QUANTITY"].sum() / 30 if not monthly_row.empty else 0
            suggested_par = round(max(weekly_avg, monthly_avg), 2)

            # Search supplier match
            supplier_match = supplier_df[supplier_df["ITEM NAME"].astype(str).str.upper().str.strip() == item_str]
            if not supplier_match.empty:
                supplier_name = supplier_file.filename.split()[0]  # e.g. 'Barakat Template.xlsx' → 'Barakat'
            else:
                supplier_name = "Unknown"

            result.append({
                "Item": item,
                "Item Code": monthly_row["ITEM CODE"].values[0] if not monthly_row.empty else "",
                "Unit": monthly_row["UNIT"].values[0] if not monthly_row.empty else "",
                "Suggested Par": suggested_par,
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": suggested_par,
                "Supplier": supplier_name
            })

        return {"data": result}

    except Exception as e:
        return {"error": str(e)}