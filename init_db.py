from project_starter import init_database, db_engine

def main():
    try:
        # Initialize the database with sample data
        init_database(db_engine)
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

if __name__ == "__main__":
    main() 