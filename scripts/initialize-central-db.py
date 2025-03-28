import os
import subprocess
import psycopg2
from dotenv import load_dotenv

# Load environment variables from admin.env
load_dotenv('admin.env')

def initialize_central_database():
    """
    Initialize the central PostgreSQL database with:
    1. Meta-schema for tracking teams and their tables
    2. Functions for team-based access control
    3. Initial admin user
    """
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_DATABASE")
    db_user = os.getenv("DB_USERNAME")
    db_password = os.getenv("DB_PASSWORD")
    
    # Connection string with SSL required for Azure
    connection_string = (
        f"host={db_host} port={db_port} dbname={db_name} "
        f"user={db_user} password={db_password} sslmode=require"
    )
    
    # SQL for initializing the central database
    init_sql = """
    -- Create a meta-schema to track information about teams and their schemas
    CREATE SCHEMA IF NOT EXISTS meta;

    -- Create table to track teams
    CREATE TABLE IF NOT EXISTS meta.teams (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        schema_name VARCHAR(100) NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create table to track users
    CREATE TABLE IF NOT EXISTS meta.users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create table to track team memberships
    CREATE TABLE IF NOT EXISTS meta.team_members (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES meta.users(id) ON DELETE CASCADE,
        team_id INTEGER NOT NULL REFERENCES meta.teams(id) ON DELETE CASCADE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, team_id)
    );

    -- Create table to track deployed tables
    CREATE TABLE IF NOT EXISTS meta.tables (
        id SERIAL PRIMARY KEY,
        team_id INTEGER NOT NULL REFERENCES meta.teams(id) ON DELETE CASCADE,
        table_name VARCHAR(100) NOT NULL,
        schema_name VARCHAR(100) NOT NULL,
        created_by INTEGER REFERENCES meta.users(id),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(schema_name, table_name)
    );

    -- Create extension for password hashing
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    -- Create initial admin user (username: admin, password: admin123)
    -- CHANGE THIS PASSWORD IN PRODUCTION!
    INSERT INTO meta.users (username, password_hash, is_admin)
    VALUES ('admin', crypt('admin123', gen_salt('bf')), true)
    ON CONFLICT (username) DO NOTHING;
    
    -- Create function to check if user is admin
    CREATE OR REPLACE FUNCTION meta.is_admin() 
    RETURNS BOOLEAN AS $$
    DECLARE
        is_admin_user BOOLEAN;
    BEGIN
        SELECT u.is_admin INTO is_admin_user
        FROM meta.users u
        WHERE u.username = current_user;
        
        RETURN COALESCE(is_admin_user, false);
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    
    -- Create function to get current user's teams
    CREATE OR REPLACE FUNCTION meta.get_user_teams() 
    RETURNS TABLE(team_id INTEGER, schema_name VARCHAR) AS $$
    DECLARE
        user_id INTEGER;
    BEGIN
        -- Get user ID
        SELECT u.id INTO user_id
        FROM meta.users u
        WHERE u.username = current_user;
        
        -- If user is admin, return all teams
        IF meta.is_admin() THEN
            RETURN QUERY 
            SELECT t.id, t.schema_name
            FROM meta.teams t;
        ELSE
            -- Otherwise, return only teams the user belongs to
            RETURN QUERY 
            SELECT t.id, t.schema_name
            FROM meta.teams t
            INNER JOIN meta.team_members tm ON t.id = tm.team_id
            WHERE tm.user_id = user_id;
        END IF;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    
    -- Function to be used by deploy.py to create tables in the correct schema
    CREATE OR REPLACE FUNCTION meta.deploy_table(
        p_team_id INTEGER,
        p_table_name VARCHAR,
        p_table_definition TEXT
    ) RETURNS BOOLEAN AS $$
    DECLARE
        user_id INTEGER;
        team_schema VARCHAR;
        create_table_sql TEXT;
        is_authorized BOOLEAN := false;
    BEGIN
        -- Check if user is authorized for this team
        SELECT COUNT(*) > 0 INTO is_authorized
        FROM meta.get_user_teams()
        WHERE team_id = p_team_id;
        
        IF NOT is_authorized THEN
            RAISE EXCEPTION 'User not authorized to deploy tables to this team';
        END IF;
        
        -- Get user ID
        SELECT u.id INTO user_id
        FROM meta.users u
        WHERE u.username = current_user;
        
        -- Get team schema
        SELECT t.schema_name INTO team_schema
        FROM meta.teams t
        WHERE t.id = p_team_id;
        
        -- Create schema if it doesn't exist
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', team_schema);
        
        -- Create the table in the team's schema
        create_table_sql := format('CREATE TABLE %I.%I %s', 
                                  team_schema, 
                                  p_table_name, 
                                  p_table_definition);
        
        EXECUTE create_table_sql;
        
        -- Log the table in meta.tables
        INSERT INTO meta.tables (team_id, table_name, schema_name, created_by)
        VALUES (p_team_id, p_table_name, team_schema, user_id)
        ON CONFLICT (schema_name, table_name) 
        DO UPDATE SET updated_at = CURRENT_TIMESTAMP;
        
        -- Grant permissions to the team members
        EXECUTE format('GRANT ALL PRIVILEGES ON %I.%I TO GROUP team_%s', 
                      team_schema, p_table_name, team_schema);
        
        RETURN true;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """
    
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
            sslmode='require'
        )
        conn.autocommit = True
        
        # Execute initialization SQL
        with conn.cursor() as cur:
            cur.execute(init_sql)
        
        conn.close()
        print("Central database initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing central database: {e}")
        return False
    
    return True

if __name__ == "__main__":
    initialize_central_database()