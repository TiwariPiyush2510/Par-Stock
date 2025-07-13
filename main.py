from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
from io import BytesIO
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_excel(file: UploadFile) -> pd.DataFrame:
    content = file.file.read()
    df = pd.read_excel(BytesIO(content))
    return df

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...),
):
    weekly_df = read_excel(weekly_file)
    monthly_df = read_excel(monthly_file)

    weekly_df["Daily Average"] = weekly_df["Qty"] / 7
    monthly_df["Daily Average"] = monthly_df["Qty"] / 30

    merged_df = pd.merge(
        weekly_df,
        monthly_df,
        on="Item Name",
        how="outer",
        suffixes=("_weekly", "_monthly"),
    )

    merged_df["Daily Average"] = merged_df[["Daily Average_weekly", "Daily Average_monthly"]].max(axis=1)
    merged_df = merged_df[["Item Name", "Item Code_weekly", "Unit_weekly", "Daily Average"]]
    merged_df.rename(columns={
        "Item Code_weekly": "Item Code",
        "Unit_weekly": "Unit",
        "Daily Average": "Suggested Par"
    }, inplace=True)

    supplier_ext = supplier_file.filename.split(".")[-1].lower()
    if supplier_ext == "csv":
        supplier_df = pd.read_csv(BytesIO(supplier_file.file.read()))
    else:
        supplier_df = read_excel(supplier_file)

    supplier_df.columns = supplier_df.columns.str.strip()
    supplier_df["Item Name"] = supplier_df["Item Name"].str.strip().str.upper()

    merged_df["Item Name"] = merged_df["Item Name"].str.strip().str.upper()
    result_df = pd.merge(merged_df, supplier_df, on="Item Name", how="inner")

    result_df["Stock in Hand"] = 0
    result_df["Expected Delivery"] = 0
    result_df["Final Stock Needed"] = result_df["Suggested Par"]
    result_df["Supplier"] = supplier_file.filename.split(".")[0]

    result_df.fillna("", inplace=True)

    return result_df.to_dict(orient="records")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)