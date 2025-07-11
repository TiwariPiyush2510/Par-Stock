from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate_par_stock/")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None),
):
    try:
        # Load weekly & monthly files
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Ensure correct columns
        required_cols = ["Item Name", "Item Code", "Unit", "Total Quantity"]
        for df in [weekly_df, monthly_df]:
            if not all(col in df.columns for col in required_cols):
                return JSONResponse(content={"error": "Missing required columns."}, status_code=400)

        # Average daily usage
        weekly_df["Daily Avg"] = weekly_df["Total Quantity"] / 7
        monthly_df["Daily Avg"] = monthly_df["Total Quantity"] / 30

        # Merge on Item Code
        merged = pd.merge(
            weekly_df[["Item Code", "Item Name", "Unit", "Daily Avg"]],
            monthly_df[["Item Code", "Daily Avg"]],
            on="Item Code",
            suffixes=("_weekly", "_monthly"),
            how="outer"
        )

        # Combine names and units
        merged["Item Name"] = merged["Item Name_weekly"].combine_first(merged["Item Name_monthly"])
        merged["Unit"] = merged["Unit_weekly"].combine_first(merged["Unit_monthly"])

        # Determine higher of the two daily averages
        merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)
        merged = merged[["Item Name", "Item Code", "Unit", "Suggested Par"]].fillna(0)

        # Load supplier templates
        supplier_map = {}

        if barakat_file:
            barakat_df = pd.read_excel(BytesIO(await barakat_file.read()))
            barakat_items = barakat_df.iloc[:, 0].astype(str).str.strip().str.lower().tolist()
            for item in barakat_items:
                supplier_map[item] = "Barakat"

        if ofi_file:
            ofi_df = pd.read_excel(BytesIO(await ofi_file.read()))
            ofi_items = ofi_df.iloc[:, 0].astype(str).str.strip().str.lower().tolist()
            for item in ofi_items:
                supplier_map[item] = "OFI"

        # Match supplier by item name
        merged["Supplier"] = merged["Item Name"].str.strip().str.lower().map(supplier_map).fillna("")

        # Round values and prepare final output
        merged["Suggested Par"] = merged["Suggested Par"].round(2)
        merged["Stock in Hand"] = 0
        merged["Final Stock Needed"] = merged["Suggested Par"]  # Placeholder; adjusted on frontend

        return merged.to_dict(orient="records")

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)