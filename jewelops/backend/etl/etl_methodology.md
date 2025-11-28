# will be performing mapping and cleaning operations on the data extracted from Google Sheets.
# such that it will be easier for LLM to process, format and understand the data.


# First Step 

# understand the tables and their columns

## expenses, sales & orders

# for Expenses table: 
# Starting and including from Epenses header column index, include 4
# - ENSURE THE ROWS FOLLOW THE SAME DATE UPTIL TOTAL-1

# for Sales table:
# Starting and including from Sales header column index, include 15
# - ENSURE THE ROWS FOLLOW THE SAME DATE UPTIL TOTAL-1

# for Orders table:
# Starting and including from Orders header column index, include 11
# - Include the same date rows UPTIL TOTAL-1

## So we are segmenting the data based on starting of date and ending at TOTAL-1 for each table
## seperate the table into two expenses and sales



# Second Step

# now that we have three tables
# Expenses & Sales table
# create a mapping version from the database types or are we expecting all to be string fields
# check are there any spaces, etc
# check the table columns for anomalies based off of mapped expected type
#    # create what type are you expecting from each column, 
#       if empty what to do
#       theres same how to reconcile them and populate empty cells
# DONE!!
# run management command for sales: 
##  python manage.py load_sales_from_csv --dry-run --errors-json=etl_errors_after_fix.json

## python manage.py load_sales_from_csv \                                                --errors-json=etl_errors_real.json
