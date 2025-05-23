from project_starter import init_database, create_engine

def main():
    # Initialize the database with sample data
    db_engine = init_database(create_engine("sqlite:///munder_difflin.db"))
    print("Database initialized successfully!")

if __name__ == "__main__":
    main() 