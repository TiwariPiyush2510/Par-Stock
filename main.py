from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
from io import BytesIO

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    # Load all files
    weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))
    
    try:
        supplier_ext = supplier_file.filename.split('.')[-1]
        if supplier_ext == 'csv':
            supplier_df = pd.read_csv(BytesIO(await supplier_file.read()))
        else:
            supplier_df = pd.read_excel(BytesIO(await supplier_file.read()))
    except:
        return {"error": "Unable to read supplier file"}

    # Clean columns
    weekly_df.columns = weekly_df.columns.str.strip()
    monthly_df.columns = monthly_df.columns.str.strip()
    supplier_df.columns = supplier_df.columns.str.strip()

    # Standardize keys
    weekly_df.rename(columns={"Item Name": "Item", "Quantity": "Weekly Qty"}, inplace=True)
    monthly_df.rename(columns={"Item Name": "Item", "Quantity": "Monthly Qty"}, inplace=True)

    # Calculate daily averages
    weekly_df["Daily Avg"] = weekly_df["Weekly Qty"] / 7
    monthly_df["Daily Avg"] = monthly_df["Monthly Qty"] / 30

    # Merge both reports
    combined = pd.merge(weekly_df[["Item", "Daily Avg"]], monthly_df[["Item", "Daily Avg"]],
                        on="Item", how="outer", suffixes=("_weekly", "_monthly"))

    combined["Suggested Par"] = combined[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1).round(2)

    # Merge supplier data
    match_column = "Item" if "Item" in supplier_df.columns else "Item Name"
    supplier_df.rename(columns={match_column: "Item"}, inplace=True)
    supplier_df["Item"] = supplier_df["Item"].str.strip().str.upper()
    combined["Item"] = combined["Item"].str.strip().str.upper()

    final_df = pd.merge(combined, supplier_df, on="Item", how="inner")

    # Select final columns
    final_df = final_df[["Item", "Item Code", "Unit", "Suggested Par"]]
    final_df["Stock in Hand"] = 0
    final_df["Expected Delivery"] = 0
    final_df["Final Stock Needed"] = 0
    final_df["Supplier"] = supplier_file.filename.split('.')[0].strip()

    return final_df.to_dict(orient="records")