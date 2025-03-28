-- EZPostgres Security Policies
-- This script sets up security policies for the central database

-- Restrict access to meta schema
REVOKE ALL ON SCHEMA meta FROM PUBLIC;

-- Secure the meta schema tables
REVOKE ALL ON ALL TABLES IN SCHEMA meta FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA meta FROM PUBLIC;

-- Create admin role
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ezpostgres_admin') THEN
        CREATE ROLE ezpostgres_admin;
    END IF;
END
$$;

-- Grant admin privileges
GRANT USAGE ON SCHEMA meta TO ezpostgres_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA meta TO ezpostgres_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA meta TO ezpostgres_admin;

-- Create user role
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ezpostgres_user') THEN
        CREATE ROLE ezpostgres_user;
    END IF;
END
$$;

-- Grant limited access to user role (only what's needed for deployment)
GRANT USAGE ON SCHEMA meta TO ezpostgres_user;
GRANT EXECUTE ON FUNCTION meta.deploy_table TO ezpostgres_user;
GRANT EXECUTE ON FUNCTION meta.get_user_teams TO ezpostgres_user;
GRANT EXECUTE ON FUNCTION meta.is_admin TO ezpostgres_user;

-- Set up row-level security on meta.tables
ALTER TABLE meta.tables ENABLE ROW LEVEL SECURITY;

-- Only allow users to see tables from their teams
CREATE POLICY tables_team_isolation ON meta.tables
    USING (team_id IN (SELECT team_id FROM meta.get_user_teams()) OR meta.is_admin())
    WITH CHECK (team_id IN (SELECT team_id FROM meta.get_user_teams()) OR meta.is_admin());

-- Set up row-level security on meta.teams
ALTER TABLE meta.teams ENABLE ROW LEVEL SECURITY;

-- Allow users to see only teams they are members of, admins see all
CREATE POLICY teams_visibility ON meta.teams
    USING (id IN (SELECT team_id FROM meta.get_user_teams()) OR meta.is_admin());

-- Set up row-level security on meta.team_members
ALTER TABLE meta.team_members ENABLE ROW LEVEL SECURITY;

-- Allow users to see only their team memberships, admins see all
CREATE POLICY team_members_visibility ON meta.team_members
    USING (team_id IN (SELECT team_id FROM meta.get_user_teams()) OR meta.is_admin());

-- Set up row-level security on meta.columns
ALTER TABLE meta.columns ENABLE ROW LEVEL SECURITY;

-- Only allow users to see columns from their teams' tables
CREATE POLICY columns_team_isolation ON meta.columns
    USING (table_id IN (
        SELECT t.id FROM meta.tables t 
        WHERE t.team_id IN (SELECT team_id FROM meta.get_user_teams())
    ) OR meta.is_admin());

-- Set up row-level security on meta.activity_log
ALTER TABLE meta.activity_log ENABLE ROW LEVEL SECURITY;

-- Allow users to see only their own activity, admins see all
CREATE POLICY activity_log_visibility ON meta.activity_log
    USING ((user_id = (SELECT id FROM meta.users WHERE username = current_user)) OR meta.is_admin());

-- Set up password complexity requirements
CREATE OR REPLACE FUNCTION meta.check_password_strength(password TEXT) 
RETURNS BOOLEAN AS $$
BEGIN
    -- Minimum length
    IF LENGTH(password) < 8 THEN
        RAISE EXCEPTION 'Password must be at least 8 characters long';
    END IF;
    
    -- Must contain at least one uppercase letter
    IF password !~ '[A-Z]' THEN
        RAISE EXCEPTION 'Password must contain at least one uppercase letter';
    END IF;
    
    -- Must contain at least one lowercase letter
    IF password !~ '[a-z]' THEN
        RAISE EXCEPTION 'Password must contain at least one lowercase letter';
    END IF;
    
    -- Must contain at least one digit
    IF password !~ '[0-9]' THEN
        RAISE EXCEPTION 'Password must contain at least one digit';
    END IF;
    
    -- Must contain at least one special character
    IF password !~ '[^a-zA-Z0-9]' THEN
        RAISE EXCEPTION 'Password must contain at least one special character';
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Trigger to enforce password policy on new users
CREATE OR REPLACE FUNCTION meta.enforce_password_policy() 
RETURNS TRIGGER AS $$
DECLARE
    password TEXT;
BEGIN
    -- Extract the password from the crypt function
    -- This is a bit of a hack, but we need to check the password before it's hashed
    password := SUBSTRING(NEW.password_hash FROM 'crypt\((.+),');
    
    -- Remove the trailing comma and single quote
    password := SUBSTRING(password FROM 1 FOR LENGTH(password) - 2);
    
    -- Check password strength
    PERFORM meta.check_password_strength(password);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add the trigger to the users table
CREATE TRIGGER enforce_password_policy_trigger
BEFORE INSERT OR UPDATE ON meta.users
FOR EACH ROW
EXECUTE FUNCTION meta.enforce_password_policy();

-- Connection rate limiting
-- This requires the pg_prewarm extension
CREATE EXTENSION IF NOT EXISTS pg_prewarm;

-- Create table to track connection attempts
CREATE TABLE IF NOT EXISTS meta.connection_attempts (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    ip_address INET NOT NULL,
    attempt_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS connection_attempts_username_ip_idx 
ON meta.connection_attempts(username, ip_address, attempt_time);

-- Function to check connection rate
CREATE OR REPLACE FUNCTION meta.check_connection_rate(username TEXT, ip_address INET)
RETURNS BOOLEAN AS $$
DECLARE
    attempt_count INTEGER;
BEGIN
    -- Count failed attempts in the last 5 minutes
    SELECT COUNT(*) INTO attempt_count
    FROM meta.connection_attempts
    WHERE username = $1
      AND ip_address = $2
      AND success = FALSE
      AND attempt_time > (CURRENT_TIMESTAMP - INTERVAL '5 minutes');
    
    -- If too many failed attempts, deny connection
    IF attempt_count > 5 THEN
        RETURN FALSE;
    END IF;
    
    -- Log successful attempt
    INSERT INTO meta.connection_attempts (username, ip_address, success)
    VALUES ($1, $2, TRUE);
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining security policies
COMMENT ON SCHEMA meta IS 'EZPostgres meta-schema for team isolation and access control';