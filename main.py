from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import pandas as pd
import io

app = FastAPI()

# CORS for Netlify
origins = ["https://preeminent-choux-a8ea17.netlify.app"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store supplier items in memory
supplier_items = {}

def read_excel_or_csv(upload_file: UploadFile) -> pd.DataFrame:
    content = upload_file.file.read()
    try:
        return pd.read_excel(io.BytesIO(content))
    except:
        return pd.read_csv(io.BytesIO(content))

def get_daily_average(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["Item Name", "Quantity"])
    grouped = df.groupby("Item Name")["Quantity"].sum().reset_index()
    grouped["Daily Avg"] = grouped["Quantity"] / 7
    return grouped[["Item Name", "Daily Avg"]]

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: Optional[UploadFile] = File(None),
    ofi_file: Optional[UploadFile] = File(None),
    alAhlia_file: Optional[UploadFile] = File(None),
    emirates_file: Optional[UploadFile] = File(None),
    harvey_file: Optional[UploadFile] = File(None),
):
    # Step 1: Read consumption files
    weekly_df = get_daily_average(read_excel_or_csv(weekly_file))
    monthly_df = get_daily_average(read_excel_or_csv(monthly_file))

    # Step 2: Use higher of weekly/monthly average
    merged = pd.merge(weekly_df, monthly_df, on="Item Name", how="outer").fillna(0)
    merged["Suggested Par"] = merged[["Daily Avg_x", "Daily Avg_y"]].max(axis=1)
    merged = merged[["Item Name", "Suggested Par"]]

    # Step 3: Combine with supplier items
    supplier_data = {
        "Barakat": barakat_file,
        "OFI": ofi_file,
        "Al Ahlia": alAhlia_file,
        "Emirates Poultry": emirates_file,
        "Harvey and Brockess": harvey_file,
    }

    results = []

    for supplier_name, supplier_file in supplier_data.items():
        if supplier_file:
            df = read_excel_or_csv(supplier_file)
            supplier_items[supplier_name] = df  # cache for filtering

            for _, row in df.iterrows():
                item_name = str(row.get("Item Name")).strip()
                unit = row.get("Unit", "")
                code = row.get("Item Code", "")

                par_row = merged[merged["Item Name"].str.strip().str.lower() == item_name.lower()]
                if not par_row.empty:
                    suggested_par = float(par_row["Suggested Par"].values[0])
                    results.append({
                        "Item": item_name,
                        "Item Code": code,
                        "Unit": unit,
                        "Suggested Par": round(suggested_par, 2),
                        "Stock in Hand": 0,
                        "Expected Delivery": 0,
                        "Final Stock Needed": round(suggested_par, 2),
                        "Supplier": supplier_name
                    })

    return results