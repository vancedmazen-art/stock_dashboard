import pandas as pd
from sqlalchemy import create_engine

# Connect to your local DB
engine = create_engine(
    "mssql+pyodbc://localhost/EGX?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
)

# Load the stock table
df = pd.read_sql("SELECT * FROM [dbo].[Scanner_History]", engine)

# Save to CSV
df.to_csv("StockQuotes.csv", index=False)
print("CSV exported successfully!")
