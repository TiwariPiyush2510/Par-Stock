from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_file(file: UploadFile) -> pd.DataFrame:
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext == ".csv":
        return pd.read_csv(file.file)
    elif ext in [".xls", ".xlsx"]:
        return pd.read_excel(file.file)
    else:
        raise ValueError("Unsupported file format")

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    try:
        weekly_df = parse_file(weekly_file)
        monthly_df = parse_file(monthly_file)
        supplier_df = parse_file(supplier_file)

        weekly_df.columns = [c.strip() for c in weekly_df.columns]
        monthly_df.columns = [c.strip() for c in monthly_df.columns]
        supplier_df.columns = [c.strip() for c in supplier_df.columns]

        # Compute daily averages
        def daily_avg(df):
            return df.groupby("Item")["Quantity"].sum() / 7

        weekly_avg = daily_avg(weekly_df)
        monthly_avg = daily_avg(monthly_df)

        par_df = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1).reset_index()
        par_df.columns = ["Item", "Suggested Par"]

        # Merge with supplier data
        merged = pd.merge(par_df, supplier_df, on="Item", how="inner")

        # Ensure all necessary columns
        if "Item Code" not in merged.columns:
            merged["Item Code"] = ""
        if "Unit" not in merged.columns:
            merged["Unit"] = ""

        merged["Stock in Hand"] = 0
        merged["Expected Delivery"] = 0
        merged["Final Stock Needed"] = 0
        merged["Supplier"] = os.path.splitext(supplier_file.filename)[0]

        return merged.to_dict(orient="records")

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)