from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

app = FastAPI()

# ✅ Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to Netlify URL
    allow_credentials=True,
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
        # Read uploaded Excel files
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Calculate daily avg from weekly and monthly
        weekly_avg = weekly_df.groupby("Item Name")["Consumption"].sum() / 7
        monthly_avg = monthly_df.groupby("Item Name")["Consumption"].sum() / 30
        suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1)

        result = []
        for item, par in suggested_par.items():
            result.append({
                "Item": item,
                "Suggested Par": round(par, 2),
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": round(par, 2),
                "Supplier": ""
            })

        df_result = pd.DataFrame(result)

        # Supplier mapping by Item Name (Barakat / OFI)
        if barakat_file:
            barakat_items = pd.read_excel(BytesIO(await barakat_file.read()))["Item Name"].str.lower().tolist()
            df_result.loc[df_result["Item"].str.lower().isin(barakat_items), "Supplier"] = "Barakat"

        if ofi_file:
            ofi_items = pd.read_excel(BytesIO(await ofi_file.read()))["Item Name"].str.lower().tolist()
            df_result.loc[df_result["Item"].str.lower().isin(ofi_items), "Supplier"] = "OFI"

        return {"result": df_result.to_dict(orient="records")}

    except Exception as e:
        return JSONResponse(status_code=422, content={"error": str(e)})