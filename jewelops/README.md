# JewelOps Backend (minimal)

Run: pip install -r backend/requirements.txt && python backend/manage.py migrate && python backend/manage.py runserver

Local POSTGRES:
brew services start postgresql@14
psql jewelops


# ETL #
## Run `python etl/transform` to load excel sheet into local server

# Run management command to process sales from csv:  
##  python manage.py load_sales_from_csv --dry-run --errors-json=etl_errors_after_fix.json
## python manage.py load_sales_from_csv --errors-json=etl_errors_real.json