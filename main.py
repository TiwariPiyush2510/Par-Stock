from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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

def read_excel(file: UploadFile):
    contents = file.file.read()
    return pd.read_excel(BytesIO(contents))

@app.post("/calculate_par_stock/")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None),
):
    weekly_df = read_excel(weekly_file)
    monthly_df = read_excel(monthly_file)

    merged = pd.merge(weekly_df, monthly_df, on="Item Name", suffixes=('_weekly', '_monthly'))

    # Calculate daily averages
    merged["Daily Avg Weekly"] = merged["Quantity_weekly"] / 7
    merged["Daily Avg Monthly"] = merged["Quantity_monthly"] / 30
    merged["Suggested Par"] = merged[["Daily Avg Weekly", "Daily Avg Monthly"]].max(axis=1).round(2)

    # Add supplier info
    merged["Supplier"] = ""

    def mark_supplier(supplier_file, supplier_name):
        if supplier_file:
            supplier_df = read_excel(supplier_file)
            supplier_items = supplier_df["Item Name"].str.strip().str.lower().tolist()
            merged.loc[
                merged["Item Name"].str.strip().str.lower().isin(supplier_items),
                "Supplier"
            ] = supplier_name

    mark_supplier(barakat_file, "Barakat")
    mark_supplier(ofi_file, "OFI")

    # Clean up for frontend
    result = merged[["Item Name", "Item Code_weekly", "Unit_weekly", "Suggested Par", "Supplier"]].copy()
    result.columns = ["Item", "Item Code", "Unit", "Suggested Par", "Supplier"]
    result["Stock in Hand"] = 0
    result["Final Stock Needed"] = result["Suggested Par"]

    return result.to_dict(orient="records")