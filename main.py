from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from typing import List
import io

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your Netlify domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    try:
        # Read consumption files
        weekly_df = pd.read_excel(io.BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(io.BytesIO(await monthly_file.read()))

        # Clean column names
        weekly_df.columns = weekly_df.columns.str.strip()
        monthly_df.columns = monthly_df.columns.str.strip()

        # Calculate daily averages
        weekly_avg = weekly_df.copy()
        weekly_avg["Daily Avg"] = weekly_avg["Quantity"] / 7
        monthly_avg = monthly_df.copy()
        monthly_avg["Daily Avg"] = monthly_avg["Quantity"] / 30

        # Merge and choose the higher average
        merged = pd.merge(
            weekly_avg,
            monthly_avg,
            on="Item Name",
            suffixes=("_weekly", "_monthly")
        )

        merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)

        # Keep necessary columns
        output_df = merged[["Item Name", "Item Code_weekly", "Unit_weekly", "Suggested Par"]].copy()
        output_df.columns = ["Item", "Item Code", "Unit", "Suggested Par"]
        output_df["Stock in Hand"] = 0
        output_df["Final Stock Needed"] = output_df["Suggested Par"]

        # Handle supplier tags
        output_df["Supplier"] = ""

        def mark_supplier(supplier_df, supplier_name):
            if supplier_df is not None:
                df = pd.read_excel(io.BytesIO(supplier_df))
                df.columns = df.columns.str.strip()
                items = df["Item Name"].str.strip().str.lower().tolist()
                output_df.loc[
                    output_df["Item"].str.strip().str.lower().isin(items), "Supplier"
                ] = supplier_name

        mark_supplier(barakat_file, "Barakat")
        mark_supplier(ofi_file, "OFI")

        # Round values
        output_df["Suggested Par"] = output_df["Suggested Par"].round(2)
        output_df["Final Stock Needed"] = output_df["Final Stock Needed"].round(2)

        return JSONResponse(content=output_df.to_dict(orient="records"))

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)