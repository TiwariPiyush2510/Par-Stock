from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate/")
async def calculate_par_stock(
    monthly_file: UploadFile = File(...),
    weekly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    # Read monthly and weekly files
    monthly_data = pd.read_excel(BytesIO(await monthly_file.read()))
    weekly_data = pd.read_excel(BytesIO(await weekly_file.read()))

    # Ensure necessary columns exist
    required_columns = ["Item Name", "Quantity"]
    if not all(col in monthly_data.columns for col in required_columns) or \
       not all(col in weekly_data.columns for col in required_columns):
        return {"error": "Missing required columns in one of the files."}

    # Clean and prepare both datasets
    def prepare_data(df):
        df = df.copy()
        df["Item Name"] = df["Item Name"].astype(str).str.strip().str.upper()
        df = df.groupby("Item Name").agg({"Quantity": "sum"}).reset_index()
        return df

    monthly_grouped = prepare_data(monthly_data)
    weekly_grouped = prepare_data(weekly_data)

    # Merge the two datasets
    merged = pd.merge(weekly_grouped, monthly_grouped, on="Item Name", how="outer", suffixes=('_weekly', '_monthly'))
    merged.fillna(0, inplace=True)

    # Calculate daily averages
    merged["Weekly Avg"] = merged["Quantity_weekly"] / 7
    merged["Monthly Avg"] = merged["Quantity_monthly"] / 30
    merged["Suggested Par"] = merged[["Weekly Avg", "Monthly Avg"]].max(axis=1).round(2)

    # Add extra columns
    merged["Stock in Hand"] = 0.0
    merged["Final Stock Needed"] = merged["Suggested Par"] * 2  # Initial placeholder

    # Try to match item details from original files
    item_details_cols = ["Item Name", "Item Code", "Unit"]
    item_details = None
    for df in [weekly_data, monthly_data]:
        if all(col in df.columns for col in item_details_cols):
            temp = df[item_details_cols].drop_duplicates().copy()
            temp["Item Name"] = temp["Item Name"].str.strip().str.upper()
            item_details = temp
            break

    if item_details is not None:
        merged = pd.merge(merged, item_details, on="Item Name", how="left")
    else:
        merged["Item Code"] = ""
        merged["Unit"] = ""

    # Supplier matching
    merged["Supplier"] = ""

    if barakat_file:
        barakat_df = pd.read_excel(BytesIO(await barakat_file.read()))
        barakat_names = set(barakat_df.iloc[:, 1].astype(str).str.strip().str.upper())
        merged.loc[merged["Item Name"].isin(barakat_names), "Supplier"] = "Barakat"

    if ofi_file:
        ofi_df = pd.read_excel(BytesIO(await ofi_file.read()))
        ofi_names = set(ofi_df.iloc[:, 1].astype(str).str.strip().str.upper())
        merged.loc[merged["Item Name"].isin(ofi_names), "Supplier"] = "OFI"

    # Recalculate Final Stock Needed using corrected formula
    merged["Final Stock Needed"] = (
        merged["Suggested Par"] * 2 - merged["Stock in Hand"]
    ).apply(lambda x: round(x if x > 0 else 0, 2))

    # Prepare final result
    result = merged[[
        "Item Name", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Final Stock Needed", "Supplier"
    ]].rename(columns={
        "Item Name": "Item",
    })

    return result.to_dict(orient="records")