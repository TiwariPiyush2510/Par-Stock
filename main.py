from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import io

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

supplier_data = {}

def read_excel_or_csv(file: UploadFile):
    content = file.file.read()
    try:
        return pd.read_excel(io.BytesIO(content))
    except Exception:
        return pd.read_csv(io.StringIO(content.decode("utf-8")))

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None),
    al_ahlia_file: UploadFile = File(None),
    emirates_file: UploadFile = File(None),
    harvey_file: UploadFile = File(None),
):
    weekly_df = read_excel_or_csv(weekly_file)
    monthly_df = read_excel_or_csv(monthly_file)

    # Preprocess & merge
    for df in [weekly_df, monthly_df]:
        df.columns = df.columns.str.strip()
    weekly_df = weekly_df.rename(columns={"Item Name": "Item"})
    monthly_df = monthly_df.rename(columns={"Item Name": "Item"})

    weekly_avg = weekly_df.groupby("Item")["Quantity"].mean() / 7
    monthly_avg = monthly_df.groupby("Item")["Quantity"].mean() / 30
    suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1).reset_index()
    suggested_par.columns = ["Item", "Suggested Par"]

    # Attach supplier info
    def process_supplier(file, name):
        if file:
            df = read_excel_or_csv(file)
            df.columns = df.columns.str.strip()
            df["Supplier"] = name
            supplier_data[name] = df
            return df
        return pd.DataFrame()

    suppliers = {
        "Barakat": barakat_file,
        "OFI": ofi_file,
        "Al Ahlia": al_ahlia_file,
        "Emirates Poultry": emirates_file,
        "Harvey and Brockess": harvey_file
    }

    all_items = []
    for name, file in suppliers.items():
        df = process_supplier(file, name)
        if not df.empty:
            all_items.append(df)

    merged = pd.concat(all_items, ignore_index=True) if all_items else pd.DataFrame(columns=["Item"])

    if merged.empty:
        return {"error": "No supplier data provided."}

    merged["Item"] = merged["Item"].str.strip().str.upper()
    suggested_par["Item"] = suggested_par["Item"].str.strip().str.upper()

    result = pd.merge(merged, suggested_par, on="Item", how="left")
    result["Suggested Par"] = result["Suggested Par"].fillna(0)
    result["Stock in Hand"] = 0
    result["Expected Delivery"] = 0

    result["Final Stock Needed"] = result["Suggested Par"]  # default until frontend fills in values

    return result.to_dict(orient="records")