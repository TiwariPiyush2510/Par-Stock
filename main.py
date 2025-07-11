from fastapi import FastAPI, UploadFile, File
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
    ofi_file: UploadFile = File(None)
):
    try:
        # Read Excel files
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Clean column names
        weekly_df.columns = [col.strip() for col in weekly_df.columns]
        monthly_df.columns = [col.strip() for col in monthly_df.columns]

        # Calculate daily averages
        weekly_df["Daily Avg"] = weekly_df["Total Quantity"] / 7
        monthly_df["Daily Avg"] = monthly_df["Total Quantity"] / 30

        # Merge based on Item Name
        merged = pd.merge(weekly_df, monthly_df, on="Item Name", suffixes=('_weekly', '_monthly'))
        merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1) * 3

        # Get final structure
        result = merged[["Item Name", "Item Code_weekly", "Unit_weekly", "Suggested Par"]].rename(
            columns={"Item Code_weekly": "Item Code", "Unit_weekly": "Unit"}
        )
        result["Stock in Hand"] = 0
        result["Final Stock Needed"] = result["Suggested Par"]
        result["Supplier"] = ""

        # Match suppliers
        if barakat_file:
            barakat_df = pd.read_excel(BytesIO(await barakat_file.read()))
            barakat_items = barakat_df["Item Name"].str.strip().str.lower().tolist()
            result["Supplier"] = result["Item Name"].str.strip().str.lower().apply(
                lambda name: "Barakat" if name in barakat_items else ""
            )

        if ofi_file:
            ofi_df = pd.read_excel(BytesIO(await ofi_file.read()))
            ofi_items = ofi_df["Item Name"].str.strip().str.lower().tolist()
            result["Supplier"] = result.apply(
                lambda row: "OFI" if row["Item Name"].strip().lower() in ofi_items else row["Supplier"],
                axis=1
            )

        return result.to_dict(orient="records")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})