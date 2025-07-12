from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import uvicorn
import os
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Unit conversion map (extend this as needed)
unit_conversion = {
    'CASE': {'KGS': 10, 'PCS': 24},
    'CS': {'KGS': 10, 'PCS': 24},
    'CS_24PCS': {'PCS': 24},
    'CS_6KGS': {'KGS': 6},
    'CS_10KGS': {'KGS': 10},
    'CS_12.5 KGS': {'KGS': 12.5},
    '5X2.5 KG': {'KGS': 12.5},
    '4 x 2.5 KG': {'KGS': 10},
    'EACH': {'EACH': 1}
}

def convert_unit(supplier_unit, target_unit):
    for base_unit, conversions in unit_conversion.items():
        if supplier_unit.upper().strip() == base_unit.upper().strip():
            return conversions.get(target_unit.upper().strip(), 1)
    return 1


def read_file(file: UploadFile):
    filename = file.filename.lower()
    content = file.file.read()
    if filename.endswith('.csv'):
        df = pd.read_csv(BytesIO(content))
    else:
        df = pd.read_excel(BytesIO(content))
    return df


def normalize_item_name(name):
    return str(name).strip().lower()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(None),
):
    try:
        weekly_df = read_file(weekly_file)
        monthly_df = read_file(monthly_file)
        supplier_df = read_file(supplier_file) if supplier_file else pd.DataFrame()

        # Normalize and calculate daily average
        weekly_df['Item Name'] = weekly_df['Item Name'].apply(normalize_item_name)
        monthly_df['Item Name'] = monthly_df['Item Name'].apply(normalize_item_name)

        weekly_avg = weekly_df.groupby('Item Name')['Quantity'].sum() / 7
        monthly_avg = monthly_df.groupby('Item Name')['Quantity'].sum() / 30

        suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1)
        suggested_par.columns = ['Weekly', 'Monthly']
        suggested_par['Suggested Par'] = suggested_par.max(axis=1).round(2)
        suggested_par.reset_index(inplace=True)

        # Add back additional columns for matching
        result = pd.merge(suggested_par, monthly_df.drop_duplicates('Item Name'), on='Item Name', how='left')

        # Supplier match
        if not supplier_df.empty:
            supplier_df['Item Name'] = supplier_df['Item Name'].apply(normalize_item_name)
            supplier_df['Supplier Unit'] = supplier_df.iloc[:, 2]  # Assuming Unit is 3rd col
            
            result = pd.merge(result, supplier_df[['Item Name', 'Supplier Unit']], on='Item Name', how='left')
            result['Supplier'] = os.path.splitext(supplier_file.filename)[0].split(" ")[0]
        else:
            result['Supplier'] = 'Unknown'

        # Calculate conversion if necessary
        result['Conversion Factor'] = result.apply(
            lambda row: convert_unit(row.get('Supplier Unit', ''), row.get('Unit', '')), axis=1
        )
        result['Suggested Par'] = (result['Suggested Par'] * result['Conversion Factor']).round(2)

        final = []
        for _, row in result.iterrows():
            final.append({
                "Item": row.get("Item Name", ""),
                "Item Code": row.get("Item Code", ""),
                "Unit": row.get("Unit", ""),
                "Suggested Par": row.get("Suggested Par", 0),
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": row.get("Suggested Par", 0),
                "Supplier": row.get("Supplier", "Unknown")
            })

        return final

    except Exception as e:
        return {"error": str(e)}

# For local testing
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)