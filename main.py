from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import uvicorn

app = FastAPI()

# Set correct CORS (no trailing slash)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://preeminent-choux-a8ea17.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_excel(file: UploadFile) -> pd.DataFrame:
    try:
        df = pd.read_excel(file.file)
        return df
    except Exception as e:
        print(f"Failed to read {file.filename}: {e}")
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(...),
    ofi_file: UploadFile = File(...)
):
    # Load files
    weekly_df = load_excel(weekly_file)
    monthly_df = load_excel(monthly_file)
    barakat_df = load_excel(barakat_file)
    ofi_df = load_excel(ofi_file)

    for df in [weekly_df, monthly_df, barakat_df, ofi_df]:
        df.columns = df.columns.str.strip().str.lower()

    # Clean barakat/ofi names
    for df in [barakat_df, ofi_df]:
        if "item name" not in df.columns:
            return {"error": "Missing 'Item Name' column in supplier file"}
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()

    # Prepare weekly/monthly
    def clean(df):
        df = df.rename(columns={"quantity": "consumption"})
        df = df[["item name", "item code", "unit", "consumption"]]
        df = df.dropna(subset=["item name"])
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()
        return df

    weekly_df = clean(weekly_df)
    monthly_df = clean(monthly_df)

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    combined = pd.merge(weekly_df, monthly_df, on="item name", how="outer", suffixes=("_weekly", "_monthly"))
    combined.fillna(0, inplace=True)
    combined["suggested par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    # Add fallback Item Code / Unit
    combined["item code"] = combined["item code_weekly"]
    combined["unit"] = combined["unit_weekly"]
    combined["item code"].fillna(combined["item code_monthly"], inplace=True)
    combined["unit"].fillna(combined["unit_monthly"], inplace=True)

    # Supplier tag
    def tag_supplier(name):
        if name in barakat_df["item name"].values:
            return "Barakat"
        elif name in ofi_df["item name"].values:
            return "OFI"
        else:
            return "Other"

    combined["supplier"] = combined["item name"].apply(tag_supplier)

    # Display formatting
    combined["item"] = combined["item name"].str.upper()
    combined["stock in hand"] = 0
    combined["expected delivery"] = 0

    # Final Stock Needed Logic
    def calc_final(suggested, stock, delivery):
        total = stock + delivery
        if total < suggested:
            return round(suggested + (suggested - total), 2)
        else:
            return round(max(0, suggested - (total - suggested)), 2)

    combined["final stock needed"] = combined.apply(
        lambda row: calc_final(row["suggested par"], row["stock in hand"], row["expected delivery"]),
        axis=1
    )

    result = combined[[
        "item", "item code", "unit", "suggested par",
        "stock in hand", "expected delivery",
        "final stock needed", "supplier"
    ]]

    return {"result": result.to_dict(orient="records")}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)