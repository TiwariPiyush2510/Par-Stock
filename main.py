from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
):
    try:
        # Read uploaded files
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Group and sum by Item and Item Code
        weekly_grouped = weekly_df.groupby(['Item', 'Item Code', 'Unit'])['Quantity'].sum().reset_index()
        monthly_grouped = monthly_df.groupby(['Item', 'Item Code', 'Unit'])['Quantity'].sum().reset_index()

        # Calculate daily average
        weekly_grouped['Weekly Avg'] = weekly_grouped['Quantity'] / 7
        monthly_grouped['Monthly Avg'] = monthly_grouped['Quantity'] / 30

        # Merge both
        merged_df = pd.merge(weekly_grouped, monthly_grouped, on=['Item', 'Item Code', 'Unit'], how='outer', suffixes=('_weekly', '_monthly'))
        merged_df.fillna(0, inplace=True)

        # Determine Suggested Par as max of both daily averages
        merged_df['Suggested Par'] = merged_df[['Weekly Avg', 'Monthly Avg']].max(axis=1)

        # Add placeholder for Stock in Hand (manually input in frontend)
        merged_df['Stock in Hand'] = 0

        # Final Stock Needed logic
        merged_df['Final Stock Needed'] = (2 * merged_df['Suggested Par'] - merged_df['Stock in Hand']).clip(lower=0)

        result = merged_df[['Item', 'Item Code', 'Unit', 'Suggested Par', 'Stock in Hand', 'Final Stock Needed']]

        return {"result": result.to_dict(orient="records")}

    except Exception as e:
        return {"error": str(e)}