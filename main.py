from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pandas as pd
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your Netlify domain for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_file(file: UploadFile) -> pd.DataFrame:
    filename = file.filename.lower()
    try:
        if filename.endswith(".csv"):
            return pd.read_csv(file.file)
        elif filename.endswith(".xlsx"):
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
    supplier_name: str = Form(...),
    supplier_file: Optional[UploadFile] = File(None)
):
    weekly_df = load_file(weekly_file)
    monthly_df = load_file(monthly_file)
    supplier_df = load_file(supplier_file) if supplier_file else pd.DataFrame()

    for df in [weekly_df, monthly_df]:
        df.columns = df.columns.str.strip().str.lower()

    if not supplier_df.empty:
        supplier_df.columns = supplier_df.columns.str.strip().str.lower()
        if "item name" in supplier_df.columns:
            supplier_df["item name"] = supplier_df["item name"].astype(str).str.lower().str.strip()
        else:
            return {"error": "Supplier file must contain 'Item Name' column"}

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

    combined = pd.merge(weekly_df, monthly_df, on="item name", suffixes=("_weekly", "_monthly"), how="outer").fillna(0)

    combined["Suggested Par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    combined["Item Code"] = combined["item code_weekly"].combine_first(combined["item code_monthly"])
    combined["Unit"] = combined["unit_weekly"].combine_first(combined["unit_monthly"])

    if not supplier_df.empty:
        combined["Supplier"] = combined["item name"].apply(
            lambda name: supplier_name if name in supplier_df["item name"].values else "Other"
        )
    else:
        combined["Supplier"] = "Unknown"

    combined["Item"] = combined["item name"].str.upper()
    combined["Stock in Hand"] = 0
    combined["Expected Delivery"] = 0
    combined["Final Stock Needed"] = combined["Suggested Par"]

    result = combined[[
        "Item", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Expected Delivery", "Final Stock Needed", "Supplier"
    ]]

    return {"result": result.to_dict(orient="records")}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)