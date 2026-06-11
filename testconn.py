import psycopg2

#DATABASE_URL = "postgresql://neondb_owner:npg_Necbgzn0LA1G@ep-round-hill-aoewpb7o-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
DATABASE_URL = "postgresql://neondb_owner:npg_Necbgzn0LA1G@ep-round-hill-aoewpb7o.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
conn = psycopg2.connect(
    DATABASE_URL,
    connect_timeout=20
)

cur = conn.cursor()
cur.execute("SELECT now();")
print(cur.fetchone())

cur.close()
conn.close()

print("OK")