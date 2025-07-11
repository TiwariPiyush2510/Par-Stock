from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import io

app = FastAPI()

origins = ["*"]  # Allow all origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

barakat_items = set()
ofi_items = set()

@app.post("/calculate")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_files: List[UploadFile] = File(None)
):
    try:
        weekly_df = pd.read_excel(io.BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(io.BytesIO(await monthly_file.read()))

        def clean_df(df):
            df.columns = df.columns.str.strip()
            return df[['Item Name', 'Item Code', 'Unit', 'Quantity']].dropna()

        weekly_df = clean_df(weekly_df)
        monthly_df = clean_df(monthly_df)

        weekly_grouped = weekly_df.groupby(['Item Name', 'Item Code', 'Unit'])['Quantity'].sum().reset_index()
        monthly_grouped = monthly_df.groupby(['Item Name', 'Item Code', 'Unit'])['Quantity'].sum().reset_index()

        weekly_grouped['Daily'] = weekly_grouped['Quantity'] / 7
        monthly_grouped['Daily'] = monthly_grouped['Quantity'] / 30

        merged = pd.merge(weekly_grouped, monthly_grouped, on=['Item Name', 'Item Code', 'Unit'], how='outer', suffixes=('_weekly', '_monthly'))
        merged.fillna(0, inplace=True)

        merged['Suggested Par'] = merged[['Daily_weekly', 'Daily_monthly']].max(axis=1).round(2)

        merged = merged[['Item Name', 'Item Code', 'Unit', 'Suggested Par']]
        merged.rename(columns={'Item Name': 'Item'}, inplace=True)

        # Process uploaded supplier templates
        global barakat_items, ofi_items
        if supplier_files:
            for f in supplier_files:
                name = f.filename.lower()
                supplier_df = pd.read_excel(io.BytesIO(await f.read()), header=None)
                supplier_df.columns = ['Item']
                items = set(supplier_df['Item'].str.strip().str.lower())

                if 'barakat' in name:
                    barakat_items = items
                elif 'ofi' in name:
                    ofi_items = items

        result = merged.to_dict(orient="records")
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

@app.get("/suppliers")
def get_suppliers():
    return {
        "barakat": list(barakat_items),
        "ofi": list(ofi_items)
    }