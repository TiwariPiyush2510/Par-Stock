from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import uvicorn
from typing import Optional
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend URL for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global cache for supplier data
supplier_cache = {}

def load_file(file: UploadFile) -> pd.DataFrame:
    try:
        if file.filename.endswith(".csv"):
            return pd.read_csv(file.file)
        else:
            return pd.read_excel(file.file)
    except Exception as e:
        print(f"Error reading {file.filename}: {e}")
        return pd.DataFrame()

def clean_consumption(df):
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={"quantity": "consumption"})
    df = df[["item name", "item code", "unit", "consumption"]]
    df = df.dropna(subset=["item name"])
    df["item name"] = df["item name"].astype(str).str.strip().str.lower()
    return df

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: Optional[UploadFile] = File(None),
    ofi_file: Optional[UploadFile] = File(None),
    ahlia_file: Optional[UploadFile] = File(None),
    poultry_file: Optional[UploadFile] = File(None),
    harvey_file: Optional[UploadFile] = File(None)
):
    # Save supplier files to cache if provided
    if barakat_file:
        supplier_cache["Barakat"] = load_file(barakat_file)
    if ofi_file:
        supplier_cache["OFI"] = load_file(ofi_file)
    if ahlia_file:
        supplier_cache["Al Ahlia"] = load_file(ahlia_file)
    if poultry_file:
        supplier_cache["Emirates Poultry"] = load_file(poultry_file)
    if harvey_file:
        supplier_cache["Harvey and Brockess"] = load_file(harvey_file)

    # Prepare supplier data (lowercase names for matching)
    for supplier, df in supplier_cache.items():
        df.columns = df.columns.str.strip().str.lower()
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()

    weekly_df = clean_consumption(load_file(weekly_file))
    monthly_df = clean_consumption(load_file(monthly_file))

    # Calculate averages
    weekly_df["daily_weekly"] = weekly_df["consumption"] / 7
    monthly_df["daily_monthly"] = monthly_df["consumption"] / 30

    combined = pd.merge(weekly_df, monthly_df, on="item name", suffixes=("_weekly", "_monthly"), how="outer")
    combined = combined.fillna(0)

    combined["Suggested Par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    combined["Item Code"] = combined["item code_weekly"].fillna(combined["item code_monthly"])
    combined["Unit"] = combined["unit_weekly"].fillna(combined["unit_monthly"])

    # Match to supplier
    def find_supplier(item_name):
        for supplier, df in supplier_cache.items():
            if item_name in df["item name"].values:
                return supplier
        return "Other"

    combined["Supplier"] = combined["item name"].apply(find_supplier)
    combined["Item"] = combined["item name"].str.upper()
    combined["Stock in Hand"] = 0
    combined["Expected Delivery"] = 0

    # Final stock logic
    combined["Final Stock Needed"] = combined["Suggested Par"]

    output = combined[[
        "Item", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Expected Delivery", "Final Stock Needed", "Supplier"
    ]]

    return {"result": output.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)