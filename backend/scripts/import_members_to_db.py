import pandas as pd
import psycopg2
from psycopg2 import Error
from psycopg2.extras import execute_values
import datetime
import uuid


def generate_uuid():
    return str(uuid.uuid4())

def update_phone_numbers():
    try:
        # Connect to Neon PostgreSQL
        conn = psycopg2.connect(DB_CONN_STRING)
        conn.autocommit = False  # We'll commit manually
        cur = conn.cursor()

        # The exact same logic as your SQL CASE expression
        update_query = """
        UPDATE members
        SET phone_number = 
            CASE 
                -- Already starts with 0 or empty/null → keep as is
                WHEN phone_number IS NULL 
                  OR phone_number = '' 
                  OR phone_number LIKE '0%' 
                    THEN phone_number
                
                -- Clean 10-digit number starting with 7,8,9 → prepend '0'
                WHEN phone_number ~ '^[789][0-9]{9}$' 
                    THEN '0' || phone_number
                
                -- Anything else → leave unchanged
                ELSE phone_number
            END
        WHERE phone_number IS NOT NULL;
        """

        # Execute the update
        cur.execute(update_query)
        updated_rows = cur.rowcount

        # Commit the transaction
        conn.commit()

        print(f"Update completed successfully.")
        print(f"Number of rows affected: {updated_rows}")

        # Optional: Preview a few updated records
        cur.execute("""
            SELECT phone_number 
            FROM members 
            WHERE phone_number IS NOT NULL 
            ORDER BY phone_number 
            LIMIT 5;
        """)
        print("\nSample of updated phone numbers:")
        for row in cur.fetchall():
            print(row[0])

    except Error as e:
        print("Error while connecting to PostgreSQL or running update:", e)
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            print("PostgreSQL connection closed.")

# ── CONFIG ───────────────────────────────────────────────────────────────
CSV_PATH = 'members_cleaned.csv'  # your local file
# Note: In production, use environment variables or a secure vault for sensitive info
DB_CONN_STRING = ''

# Column mapping: CSV → DB
COLUMN_MAP = {
    'first_name':     'first_name',
    'last_name':      'last_name',
    'Phone Number':   'phone_number',
    'Email':          'email',
    'Sex':            'gender',
    'Marital Status': 'marital_status',
    # 'Membership Type' is used for logic, not direct column
}

# ── LOAD & TRANSFORM CSV ─────────────────────────────────────────────────
df = pd.read_csv(CSV_PATH)

# Drop unwanted column if still present
if 'Full Name' in df.columns:
    df = df.drop(columns=['Full Name'])

# Rename to DB-friendly names
df = df.rename(columns=COLUMN_MAP)

# Clean/transform data
df['gender'] = df['gender'].str.strip().str.lower().replace({'male': 'M', 'female': 'F', '': None})

# Map Membership Type → first_timer boolean
df['first_timer'] = df['Membership Type'].str.strip().str.lower().isin(['first timer']).astype(bool)

# Remove the original Membership Type column (no longer needed)
df = df.drop(columns=['Membership Type'], errors='ignore')

# Add/set defaults for other columns
df['id'] = df.apply(lambda row: generate_uuid(), axis=1)
df['created_at']   = datetime.datetime.now().isoformat()  # or pd.Timestamp.now()
df['connect_name'] = None
df['date_joined']  = datetime.datetime.now().isoformat()

# Select only DB columns
db_columns = [
    'id', 'first_name', 'last_name', 'phone_number', 'email', 'created_at',
    'gender', 'marital_status', 'first_timer', 'connect_name', 'date_joined'
]
df = df.reindex(columns=db_columns, fill_value=None)


# ── INSERT INTO NEON ─────────────────────────────────────────────────────
conn = psycopg2.connect(DB_CONN_STRING)
cur = conn.cursor()

print("Inserting into columns:", db_columns)

insert_query = f"""
    INSERT INTO members ({', '.join(db_columns)})
    VALUES %s
    ON CONFLICT (email) DO NOTHING;  -- skip existing emails
"""

records = [tuple(x) for x in df.to_numpy()]
print("Sample row:", records[0] if records else "No records")

execute_values(cur, insert_query, records)

conn.commit()
cur.close()
conn.close()

update_phone_numbers()  

print(f"Successfully inserted/processed {len(records)} rows!")
