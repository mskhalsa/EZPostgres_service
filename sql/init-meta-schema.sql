-- EZPostgres Meta-Schema Initialization
-- This script creates the meta-schema structure for the central database

-- Create meta schema
CREATE SCHEMA IF NOT EXISTS meta;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create table to track teams
CREATE TABLE IF NOT EXISTS meta.teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    schema_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create table to track users
CREATE TABLE IF NOT EXISTS meta.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    email VARCHAR(255)
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
    estimated_rows INTEGER,
    last_analyzed TIMESTAMP,
    UNIQUE(schema_name, table_name)
);

-- Create table to track table columns (optional, for enhanced metadata)
CREATE TABLE IF NOT EXISTS meta.columns (
    id SERIAL PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES meta.tables(id) ON DELETE CASCADE,
    column_name VARCHAR(100) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    is_nullable BOOLEAN NOT NULL,
    column_default TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_id, column_name)
);

-- Create logging table for significant events
CREATE TABLE IF NOT EXISTS meta.activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES meta.users(id),
    activity_type VARCHAR(50) NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    object_id INTEGER,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create initial admin user (insecure default, must be changed)
INSERT INTO meta.users (username, password_hash, is_admin)
VALUES ('admin', crypt('admin123', gen_salt('bf')), true)
ON CONFLICT (username) DO NOTHING;

-- Create functions for team-based access control
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

-- Function to get current user's teams
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

-- Function to deploy a table (used by deploy.py)
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
    
    -- Log activity
    INSERT INTO meta.activity_log (user_id, activity_type, object_type, object_id, description)
    VALUES (
        user_id, 
        'CREATE', 
        'TABLE', 
        (SELECT id FROM meta.tables WHERE schema_name = team_schema AND table_name = p_table_name),
        format('Created or updated table %I.%I', team_schema, p_table_name)
    );
    
    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update last login time
CREATE OR REPLACE FUNCTION meta.update_last_login() RETURNS TRIGGER AS $$
BEGIN
    UPDATE meta.users 
    SET last_login = CURRENT_TIMESTAMP
    WHERE username = current_user;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update last login time on connection
CREATE TRIGGER update_last_login_trigger
AFTER CONNECT ON DATABASE current_database()
EXECUTE FUNCTION meta.update_last_login();

-- Create view for easier reporting
CREATE OR REPLACE VIEW meta.team_statistics AS
SELECT 
    t.id AS team_id,
    t.name AS team_name,
    t.schema_name,
    COUNT(DISTINCT tm.user_id) AS user_count,
    COUNT(DISTINCT tbl.id) AS table_count,
    MAX(tbl.updated_at) AS last_activity
FROM meta.teams t
LEFT JOIN meta.team_members tm ON t.id = tm.team_id
LEFT JOIN meta.tables tbl ON t.id = tbl.team_id
GROUP BY t.id, t.name, t.schema_name;

-- Create view for auditing purposes
CREATE OR REPLACE VIEW meta.recent_activity AS
SELECT 
    al.id,
    u.username,
    al.activity_type,
    al.object_type,
    al.description,
    al.created_at
FROM meta.activity_log al
JOIN meta.users u ON al.user_id = u.id
ORDER BY al.created_at DESC
LIMIT 100;