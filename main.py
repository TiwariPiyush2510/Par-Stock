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
    # Load and normalize
    weekly_df = load_excel(weekly_file)
    monthly_df = load_excel(monthly_file)
    barakat_df = load_excel(barakat_file)
    ofi_df = load_excel(ofi_file)

    for df in [weekly_df, monthly_df]:
        df.columns = df.columns.str.strip().str.lower()

    for df in [barakat_df, ofi_df]:
        df.columns = df.columns.str.strip().str.lower()
        if "item name" not in df.columns:
            return {"error": "Item Name column missing in supplier template"}
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()

    # Clean and compute daily average
    def clean(df):
        df = df.rename(columns={"quantity": "Consumption"})
        df = df[["item name", "item code", "unit", "Consumption"]]
        df = df.dropna(subset=["item name"])
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()
        return df

    weekly_df = clean(weekly_df)
    monthly_df = clean(monthly_df)

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    combined = pd.merge(weekly_df, monthly_df, on="item name", suffixes=("_weekly", "_monthly"), how="outer").fillna(0)
    combined["Suggested Par"] = combined[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    combined["Item Code"] = combined["item code_weekly"]
    combined["Unit"] = combined["unit_weekly"]
    combined["Item Code"].fillna(combined["item code_monthly"], inplace=True)
    combined["Unit"].fillna(combined["unit_monthly"], inplace=True)

    # Tag suppliers
    def match_supplier(name):
        if name in barakat_df["item name"].values:
            return "Barakat"
        elif name in ofi_df["item name"].values:
            return "OFI"
        else:
            return "Other"

    combined["Supplier"] = combined["item name"].apply(match_supplier)

    combined["Item"] = combined["item name"].str.upper()
    combined["Stock in Hand"] = 0
    combined["Expected Delivery"] = 0

    # Apply final stock logic
    def calculate_final_stock(row):
        p = row["Suggested Par"]
        s = row["Stock in Hand"]
        d = row["Expected Delivery"]
        total = s + d
        if total < p:
            return round(p + (p - total), 2)
        else:
            return round(max(0, p - (total - p)), 2)

    combined["Final Stock Needed"] = combined.apply(calculate_final_stock, axis=1)

    output = combined[[
        "Item", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Expected Delivery",
        "Final Stock Needed", "Supplier"
    ]]

    return {"result": output.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)