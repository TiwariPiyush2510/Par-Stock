from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import io
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store supplier data globally
supplier_data = {}

# Try reading Excel or CSV from UploadFile
def read_file(file: UploadFile):
    content = file.file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
    except:
        df = pd.read_csv(io.BytesIO(content))
    return df

def calculate_daily_avg(df):
    df = df.copy()
    df['Daily Average'] = df['Quantity'] / df['Days']
    return df[['Item Name', 'Daily Average']]

def get_higher_daily_avg(weekly_df, monthly_df):
    weekly_df = calculate_daily_avg(weekly_df)
    monthly_df = calculate_daily_avg(monthly_df)
    combined = pd.merge(weekly_df, monthly_df, on='Item Name', how='outer', suffixes=('_weekly', '_monthly'))
    combined = combined.fillna(0)
    combined['Suggested Par'] = combined[['Daily Average_weekly', 'Daily Average_monthly']].max(axis=1).round(2)
    return combined[['Item Name', 'Suggested Par']]

def load_supplier_data(supplier_file: UploadFile):
    df = read_file(supplier_file)
    df.columns = df.columns.str.strip()
    df['Item Name'] = df['Item Name'].astype(str).str.strip().str.upper()
    df['Unit'] = df['Unit'].astype(str).str.strip().str.upper()
    return df

def match_items(par_df, supplier_df):
    supplier_df['Item Name'] = supplier_df['Item Name'].astype(str).str.upper()
    par_df['Item Name'] = par_df['Item Name'].astype(str).str.upper()
    merged = pd.merge(par_df, supplier_df, on='Item Name', how='inner')
    merged = merged.rename(columns={
        'Unit': 'Unit',
        'Item Code': 'Item Code'
    })
    merged['Stock in Hand'] = 0
    merged['Expected Delivery'] = 0
    merged['Final Stock Needed'] = merged['Suggested Par']
    merged['Supplier'] = supplier_df.get('Supplier', 'N/A')
    return merged[['Item Name', 'Item Code', 'Unit', 'Suggested Par', 'Stock in Hand', 'Expected Delivery', 'Final Stock Needed', 'Supplier']]

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    try:
        weekly_df = pd.read_excel(weekly_file.file)
        monthly_df = pd.read_excel(monthly_file.file)
    except:
        return {"error": "Invalid weekly or monthly file format."}

    weekly_df = weekly_df.rename(columns=lambda x: x.strip())
    monthly_df = monthly_df.rename(columns=lambda x: x.strip())

    weekly_df['Days'] = 7
    monthly_df['Days'] = 30

    par_df = get_higher_daily_avg(weekly_df, monthly_df)

    supplier_df = load_supplier_data(supplier_file)
    supplier_name = supplier_file.filename.split()[0].strip().lower()
    supplier_data[supplier_name] = supplier_df

    merged_df = match_items(par_df, supplier_df)

    records = merged_df.fillna("").to_dict(orient='records')
    return {"data": records}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)