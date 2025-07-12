from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import Optional
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_file(file: Optional[UploadFile]) -> pd.DataFrame:
    if not file:
        return pd.DataFrame()
    filename = file.filename.lower()
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file.file)
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file.file)
        else:
            return pd.DataFrame()
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: Optional[UploadFile] = File(None),
    ofi_file: Optional[UploadFile] = File(None),
    al_ahlia_file: Optional[UploadFile] = File(None),
    ep_file: Optional[UploadFile] = File(None),
    hb_file: Optional[UploadFile] = File(None),
):
    # Load consumption data
    weekly_df = load_file(weekly_file)
    monthly_df = load_file(monthly_file)

    for df in [weekly_df, monthly_df]:
        df.rename(columns={"quantity": "consumption"}, inplace=True)
        df["item name"] = df["item name"].astype(str).str.lower().str.strip()

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    combined = pd.merge(
        weekly_df, monthly_df, on="item name", how="outer", suffixes=("_weekly", "_monthly")
    ).fillna(0)

    combined["Suggested Par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)
    combined["Item Code"] = combined["item code_weekly"].fillna(combined["item code_monthly"])
    combined["Unit"] = combined["unit_weekly"].fillna(combined["unit_monthly"])
    combined["Item"] = combined["item name"].str.upper()
    combined["Stock in Hand"] = 0
    combined["Expected Delivery"] = 0
    combined["Final Stock Needed"] = combined["Suggested Par"]

    # Load supplier files
    suppliers = {
        "Barakat": load_file(barakat_file),
        "OFI": load_file(ofi_file),
        "Al Ahlia": load_file(al_ahlia_file),
        "Emirates Poultry": load_file(ep_file),
        "Harvey and Brockess": load_file(hb_file),
    }

    for name, df in suppliers.items():
        if not df.empty:
            df["item name"] = df["item name"].astype(str).str.lower().str.strip()
            combined.loc[combined["item name"].isin(df["item name"]), "Supplier"] = name

    combined["Supplier"] = combined["Supplier"].fillna("Other")

    result = combined[[
        "Item", "Item Code", "Unit", "Suggested Par", "Stock in Hand",
        "Expected Delivery", "Final Stock Needed", "Supplier"
    ]]

    return {"result": result.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)