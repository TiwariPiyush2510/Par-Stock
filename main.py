from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_file(file: UploadFile) -> pd.DataFrame:
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        print(f"Error reading file {file.filename}: {e}")
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    weekly_df = load_file(weekly_file)
    monthly_df = load_file(monthly_file)
    supplier_df = load_file(supplier_file)

    supplier_df["item name"] = supplier_df["item name"].astype(str).str.strip().str.lower()

    def clean(df):
        df = df.rename(columns={"quantity": "consumption"})
        df = df[["item name", "item code", "unit", "consumption"]]
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()
        return df.dropna(subset=["item name"])

    weekly_df = clean(weekly_df)
    monthly_df = clean(monthly_df)

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    combined = pd.merge(weekly_df, monthly_df, on="item name", how="outer", suffixes=("_weekly", "_monthly"))
    combined = combined.fillna(0)
    combined["suggested par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    combined["item code"] = combined["item code_weekly"].combine_first(combined["item code_monthly"])
    combined["unit"] = combined["unit_weekly"].combine_first(combined["unit_monthly"])

    # Match supplier
    def get_supplier(name):
        if name in supplier_df["item name"].values:
            return supplier_df[supplier_df["item name"] == name].get("supplier", pd.Series(["Unknown"])).values[0]
        return "Unknown"

    combined["supplier"] = combined["item name"].apply(get_supplier)

    combined["item"] = combined["item name"].str.upper()
    combined["stock in hand"] = 0
    combined["expected delivery"] = 0
    combined["final stock needed"] = combined["suggested par"]

    output = combined[[
        "item", "item code", "unit", "suggested par",
        "stock in hand", "expected delivery", "final stock needed", "supplier"
    ]].rename(columns={
        "item": "Item", "item code": "Item Code", "unit": "Unit",
        "suggested par": "Suggested Par", "stock in hand": "Stock in Hand",
        "expected delivery": "Expected Delivery", "final stock needed": "Final Stock Needed",
        "supplier": "Supplier"
    })

    return output.to_dict(orient="records")