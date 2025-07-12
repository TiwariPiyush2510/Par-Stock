from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with your Netlify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(upload: UploadFile) -> pd.DataFrame:
    try:
        if upload.filename.endswith(".csv"):
            return pd.read_csv(upload.file)
        else:
            return pd.read_excel(upload.file)
    except Exception as e:
        print(f"Error reading {upload.filename}: {e}")
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None),
    ahlia_file: UploadFile = File(None),
    epoultry_file: UploadFile = File(None),
    harvey_file: UploadFile = File(None)
):
    supplier_files = {
        "Barakat": barakat_file,
        "OFI": ofi_file,
        "Al Ahlia": ahlia_file,
        "Emirates Poultry": epoultry_file,
        "Harvey and Brockess": harvey_file
    }

    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)

    weekly_df.columns = weekly_df.columns.str.strip().str.lower()
    monthly_df.columns = monthly_df.columns.str.strip().str.lower()

    def clean(df):
        df = df.rename(columns={"quantity": "consumption"})
        df = df[["item name", "item code", "unit", "consumption"]]
        df["item name"] = df["item name"].str.strip().str.lower()
        return df.dropna()

    weekly_df = clean(weekly_df)
    monthly_df = clean(monthly_df)

    weekly_df["daily"] = weekly_df["consumption"] / 7
    monthly_df["daily"] = monthly_df["consumption"] / 30

    merged = pd.merge(weekly_df, monthly_df, on="item name", suffixes=("_weekly", "_monthly"), how="outer")
    merged = merged.fillna(0)

    merged["suggested par"] = merged[["daily_weekly", "daily_monthly"]].max(axis=1).round(2)

    merged["item code"] = merged["item code_weekly"].combine_first(merged["item code_monthly"])
    merged["unit"] = merged["unit_weekly"].combine_first(merged["unit_monthly"])
    merged["item"] = merged["item name"].str.upper()

    merged["stock in hand"] = 0
    merged["expected delivery"] = 0
    merged["final stock needed"] = merged["suggested par"]

    # Supplier tagging
    def identify_supplier(name):
        name = name.lower().strip()
        for supplier, file in supplier_files.items():
            if file:
                df = read_file(file)
                df.columns = df.columns.str.strip().str.lower()
                if "item name" in df.columns:
                    df["item name"] = df["item name"].astype(str).str.lower().str.strip()
                    if name in df["item name"].values:
                        return supplier
        return "Other"

    merged["supplier"] = merged["item name"].apply(identify_supplier)

    result = merged[[
        "item", "item code", "unit", "suggested par",
        "stock in hand", "expected delivery",
        "final stock needed", "supplier"
    ]]

    return {"result": result.to_dict(orient="records")}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)