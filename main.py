from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import List
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_file(file: UploadFile) -> pd.DataFrame:
    if file.filename.endswith(".csv"):
        return pd.read_csv(file.file)
    return pd.read_excel(file.file)

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...),
):
    weekly_df = parse_file(weekly_file)
    monthly_df = parse_file(monthly_file)
    supplier_df = parse_file(supplier_file)

    weekly_avg = weekly_df.groupby("Item Name")["Quantity"].sum() / 7
    monthly_avg = monthly_df.groupby("Item Name")["Quantity"].sum() / 30

    suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1).reset_index()
    suggested_par.columns = ["Item", "Suggested Par"]

    final_df = supplier_df.copy()
    final_df["Item"] = final_df["Item"].str.strip().str.upper()

    merged = pd.merge(final_df, suggested_par, how="left", left_on="Item", right_on="Item")
    merged["Suggested Par"] = merged["Suggested Par"].fillna(0)

    merged = merged[["Item", "Item Code", "Unit", "Suggested Par"]]
    merged["Stock in Hand"] = 0
    merged["Expected Delivery"] = 0
    merged["Final Stock Needed"] = 0
    merged["Supplier"] = supplier_file.filename.split(".")[0]

    return merged.to_dict(orient="records")

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)