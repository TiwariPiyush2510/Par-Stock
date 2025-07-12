from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your Netlify domain for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(file: UploadFile) -> pd.DataFrame:
    filename = file.filename.lower()
    try:
        if filename.endswith('.csv'):
            return pd.read_csv(file.file)
        elif filename.endswith(('.xls', '.xlsx')):
            return pd.read_excel(file.file)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Failed to read {file.filename}: {e}")
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    # Normalize column names
    for df in [weekly_df, monthly_df, supplier_df]:
        df.columns = df.columns.str.strip().str.lower()

    # Clean consumption data
    def clean(df):
        df = df.rename(columns={"quantity": "consumption"})
        df = df[["item name", "item code", "unit", "consumption"]]
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()
        return df.dropna(subset=["item name"])

    weekly_df = clean(weekly_df)
    monthly_df = clean(monthly_df)

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    combined = pd.merge(weekly_df, monthly_df, on="item name", suffixes=("_weekly", "_monthly"), how="outer").fillna(0)
    combined["suggested par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    # Backfill item code and unit
    combined["item code"] = combined["item code_weekly"].combine_first(combined["item code_monthly"])
    combined["unit"] = combined["unit_weekly"].combine_first(combined["unit_monthly"])

    # Normalize supplier data
    supplier_df["item name"] = supplier_df["item name"].astype(str).str.strip().str.lower()

    # Detect supplier name
    supplier_name = "Unknown"
    for known in ["barakat", "ofi", "al ahlia", "emirates poultry", "harvey and brockess"]:
        if known in supplier_file.filename.lower():
            supplier_name = known.title()
            break

    # Match items to supplier
    combined["supplier"] = combined["item name"].apply(
        lambda x: supplier_name if x in supplier_df["item name"].values else "Other"
    )

    # Convert UOM if needed (e.g. from supplier CASE to KG)
    uom_map = {}
    if "unit" in supplier_df.columns:
        for _, row in supplier_df.iterrows():
            uom_map[row["item name"]] = row["unit"]

    # Optionally: apply conversion factor if needed
    # (e.g. if CASE needs to be converted to KG based on mapping)
    # This example assumes supplier unit is correct but you can enhance this

    combined["item"] = combined["item name"].str.upper()
    combined["stock in hand"] = 0
    combined["expected delivery"] = 0

    def calculate_final(row):
        par = row["suggested par"]
        total_stock = row["stock in hand"] + row["expected delivery"]
        if total_stock < par:
            return round(par + (par - total_stock), 2)
        else:
            return round(max(0, par - (total_stock - par)), 2)

    combined["final stock needed"] = combined.apply(calculate_final, axis=1)

    output = combined[[
        "item", "item code", "unit", "suggested par",
        "stock in hand", "expected delivery", "final stock needed", "supplier"
    ]]

    return output.to_dict(orient="records")