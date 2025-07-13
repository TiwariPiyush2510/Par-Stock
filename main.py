from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_suggested_par(weekly_df, monthly_df):
    weekly_avg = weekly_df.groupby("Item Name")["Quantity"].sum() / 7
    monthly_avg = monthly_df.groupby("Item Name")["Quantity"].sum() / 30
    final_avg = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1)
    return final_avg.reset_index(name="Suggested Par")

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...),
):
    weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

    par_df = calculate_suggested_par(weekly_df, monthly_df)

    supplier_ext = supplier_file.filename.split(".")[-1].lower()
    if supplier_ext == "csv":
        supplier_df = pd.read_csv(BytesIO(await supplier_file.read()))
    else:
        supplier_df = pd.read_excel(BytesIO(await supplier_file.read()))

    supplier_df["Item Name"] = supplier_df["Item Name"].str.strip().str.upper()
    par_df["Item Name"] = par_df["Item Name"].str.strip().str.upper()

    merged = pd.merge(par_df, supplier_df, on="Item Name", how="inner")

    merged.fillna("", inplace=True)

    result = merged[[
        "Item Name", "Item Code", "Unit", "Suggested Par"
    ]].copy()

    result["Stock in Hand"] = 0
    result["Expected Delivery"] = 0
    result["Final Stock Needed"] = 0
    result["Supplier"] = supplier_file.filename.split(".")[0]  # e.g., "Barakat Template" => "Barakat Template"

    return JSONResponse(content=result.to_dict(orient="records"))