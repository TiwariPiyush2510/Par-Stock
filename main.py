# --- main.py ---
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from typing import List
import io

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conversion logic
unit_conversion = {
    "CS_24PCS": 24,
    "CS_6BTL": 6,
    "CS_24BTL": 24,
    "CS_12BTL": 12,
    "BIB_10LTR": 10,
    "BIB_19LTR": 19,
    "CS_24BTL X 290ML": 24,
    "CS_1ltr x 12btls": 12,
    # Add more if needed
}

def clean_item_name(name):
    return str(name).strip().lower()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    try:
        weekly_df = pd.read_excel(weekly_file.file)
        monthly_df = pd.read_excel(monthly_file.file)

        # Support CSV or Excel for supplier
        if supplier_file.filename.endswith(".csv"):
            supplier_df = pd.read_csv(supplier_file.file)
        else:
            supplier_df = pd.read_excel(supplier_file.file)

        # Clean up item names
        weekly_df['Item Name Clean'] = weekly_df['Item Name'].apply(clean_item_name)
        monthly_df['Item Name Clean'] = monthly_df['Item Name'].apply(clean_item_name)
        supplier_df['Item Name Clean'] = supplier_df['Item Name'].apply(clean_item_name)

        # Merge reports
        combined_df = pd.concat([weekly_df, monthly_df])

        par_data = []

        for item_name in combined_df['Item Name Clean'].unique():
            weekly = weekly_df[weekly_df['Item Name Clean'] == item_name]['Quantity'].sum()
            monthly = monthly_df[monthly_df['Item Name Clean'] == item_name]['Quantity'].sum()

            weekly_avg = weekly / 7
            monthly_avg = monthly / 30
            suggested_par = round(max(weekly_avg, monthly_avg), 2)

            original_row = combined_df[combined_df['Item Name Clean'] == item_name].iloc[0]
            supplier_row = supplier_df[supplier_df['Item Name Clean'] == item_name]

            item_code = original_row.get("Item Code", "")
            unit = original_row.get("Unit", "")

            # Handle supplier unit conversion
            if not supplier_row.empty:
                sup_unit = str(supplier_row.iloc[0].get("Unit Price", "")).strip().upper()
                conversion_rate = unit_conversion.get(sup_unit, 1)
                suggested_par = round(suggested_par / conversion_rate, 2)
                supplier_name = supplier_file.filename.split(".")[0]
            else:
                supplier_name = "Unknown"

            par_data.append({
                "Item": original_row.get("Item Name", ""),
                "Item Code": item_code,
                "Unit": unit,
                "Suggested Par": suggested_par,
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": suggested_par,
                "Supplier": supplier_name
            })

        return JSONResponse(content=par_data)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})