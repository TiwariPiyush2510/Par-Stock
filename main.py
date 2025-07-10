from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(weekly_file: UploadFile = File(...), monthly_file: UploadFile = File(...)):
    try:
        # Read uploaded files
        weekly_content = await weekly_file.read()
        monthly_content = await monthly_file.read()
        weekly_df = pd.read_excel(BytesIO(weekly_content))
        monthly_df = pd.read_excel(BytesIO(monthly_content))

        # Ensure column names
        required_columns = ["Item", "Item Code", "Unit", "Quantity"]
        if not all(col in weekly_df.columns for col in required_columns) or not all(col in monthly_df.columns for col in required_columns):
            return {"error": "Missing required columns in uploaded files."}

        # Group and sum
        weekly_grouped = weekly_df.groupby(["Item", "Item Code", "Unit"])["Quantity"].sum().reset_index()
        monthly_grouped = monthly_df.groupby(["Item", "Item Code", "Unit"])["Quantity"].sum().reset_index()

        # Daily averages
        weekly_grouped["Weekly_Avg"] = weekly_grouped["Quantity"] / 7
        monthly_grouped["Monthly_Avg"] = monthly_grouped["Quantity"] / 30

        # Merge
        merged = pd.merge(weekly_grouped, monthly_grouped, on=["Item", "Item Code", "Unit"], how="outer")
        merged.fillna(0, inplace=True)

        # Suggested Par = max(weekly_avg, monthly_avg)
        merged["Suggested Par"] = merged[["Weekly_Avg", "Monthly_Avg"]].max(axis=1).round(2)

        # Final output
        result = merged[["Item", "Item Code", "Unit", "Suggested Par"]].to_dict(orient="records")
        return {"result": result}

    except Exception as e:
        return {"error": str(e)}