import config
import mysql.connector

print("Starting DB test...")

conn = mysql.connector.connect(
    host=config.DB_HOST,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    database=config.DB_NAME,
    connection_timeout=5,
    use_pure=True
)

print("Connected:", conn.is_connected())

conn.close()

print("DB test completed.")