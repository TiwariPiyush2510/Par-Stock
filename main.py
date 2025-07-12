# main.py (FastAPI Backend for Par Stock Calculator)

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import uvicorn

app = FastAPI()

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
    # Load uploaded files
    weekly_df = load_excel(weekly_file)
    monthly_df = load_excel(monthly_file)
    barakat_df = load_excel(barakat_file)
    ofi_df = load_excel(ofi_file)

    # Clean column names
    for df in [weekly_df, monthly_df, barakat_df, ofi_df]:
        df.columns = df.columns.str.strip().str.lower()

    for df in [barakat_df, ofi_df]:
        if "item name" not in df.columns:
            return {"error": "Item Name column missing in supplier file"}
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()

    # Prepare weekly and monthly
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

    combined = pd.merge(
        weekly_df, monthly_df,
        on="item name", suffixes=("_weekly", "_monthly"),
        how="outer"
    ).fillna(0)

    combined["Suggested Par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    # Fallback for code/unit
    combined["Item Code"] = combined["item code_weekly"]
    combined["Unit"] = combined["unit_weekly"]
    combined["Item Code"].fillna(combined["item code_monthly"], inplace=True)
    combined["Unit"].fillna(combined["unit_monthly"], inplace=True)

    # Tag supplier
    def match_supplier(name):
        if name in barakat_df["item name"].values:
            return "Barakat"
        elif name in ofi_df["item name"].values:
            return "OFI"
        else:
            return "Other"

    combined["Supplier"] = combined["item name"].apply(match_supplier)

    # Final output
    combined["Item"] = combined["item name"].str.upper()
    combined["Stock in Hand"] = 0
    combined["Expected Delivery"] = 0
    combined["Final Stock Needed"] = combined["Suggested Par"]

    result = combined[[
        "Item", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Expected Delivery",
        "Final Stock Needed", "Supplier"
    ]]

    return {"result": result.to_dict(orient="records")}


if __name__ == "__main__":
    # Required for Render deployment
    uvicorn.run("main:app", host="0.0.0.0", port=10000)