from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(upload: UploadFile) -> pd.DataFrame:
    try:
        if upload.filename.endswith(".csv"):
            return pd.read_csv(upload.file)
        elif upload.filename.endswith(".xlsx"):
            return pd.read_excel(upload.file)
        else:
            print(f"Unsupported file format: {upload.filename}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error reading file {upload.filename}: {e}")
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(...),
    ofi_file: UploadFile = File(...),
    al_ahlia_file: UploadFile = File(...),
    ep_file: UploadFile = File(...),
    hb_file: UploadFile = File(...)
):
    # Load all files
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    barakat_df = read_file(barakat_file)
    ofi_df = read_file(ofi_file)
    al_ahlia_df = read_file(al_ahlia_file)
    ep_df = read_file(ep_file)
    hb_df = read_file(hb_file)

    # Clean and normalize
    for df in [weekly_df, monthly_df]:
        df.columns = df.columns.str.strip().str.lower()

    def prepare_supplier(df):
        df.columns = df.columns.str.strip().str.lower()
        if "item name" in df.columns:
            df["item name"] = df["item name"].astype(str).str.strip().str.lower()
        return df

    supplier_dfs = {
        "Barakat": prepare_supplier(barakat_df),
        "OFI": prepare_supplier(ofi_df),
        "Al Ahlia": prepare_supplier(al_ahlia_df),
        "Emirates Poultry": prepare_supplier(ep_df),
        "Harvey and Brockess": prepare_supplier(hb_df),
    }

    # Clean consumption data
    def clean_consumption(df):
        df = df.rename(columns={"quantity": "consumption"})
        df = df[["item name", "item code", "unit", "consumption"]]
        df.dropna(subset=["item name"], inplace=True)
        df["item name"] = df["item name"].astype(str).str.strip().str.lower()
        return df

    weekly_df = clean_consumption(weekly_df)
    monthly_df = clean_consumption(monthly_df)

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    merged = pd.merge(
        weekly_df, monthly_df, on="item name", suffixes=("_weekly", "_monthly"), how="outer"
    ).fillna(0)

    merged["Suggested Par"] = merged[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    # Fill item code and unit
    merged["Item Code"] = merged["item code_weekly"]
    merged["Unit"] = merged["unit_weekly"]
    merged["Item Code"].fillna(merged["item code_monthly"], inplace=True)
    merged["Unit"].fillna(merged["unit_monthly"], inplace=True)

    # Assign supplier
    def get_supplier(name):
        for supplier, df in supplier_dfs.items():
            if name in df["item name"].values:
                return supplier
        return "Other"

    merged["Supplier"] = merged["item name"].apply(get_supplier)

    # Initialize stock fields
    merged["Item"] = merged["item name"].str.upper()
    merged["Stock in Hand"] = 0
    merged["Expected Delivery"] = 0
    merged["Final Stock Needed"] = merged["Suggested Par"]

    final = merged[[
        "Item", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Expected Delivery", "Final Stock Needed", "Supplier"
    ]]

    return {"result": final.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)