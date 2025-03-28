import os
import argparse
import psycopg2
import getpass
from tabulate import tabulate
from dotenv import load_dotenv

# Load environment variables from admin.env
load_dotenv('admin.env')

def connect_to_db():
    """Connect to the PostgreSQL database as admin."""
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_DATABASE")
    db_user = os.getenv("DB_USERNAME")
    db_password = os.getenv("DB_PASSWORD")
    
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
        sslmode='require'
    )
    
    return conn

def list_teams():
    """List all teams in the database."""
    try:
        conn = connect_to_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.name, t.schema_name, COUNT(tm.user_id) as members,
                       COUNT(tbl.id) as tables
                FROM meta.teams t
                LEFT JOIN meta.team_members tm ON t.id = tm.team_id
                LEFT JOIN meta.tables tbl ON t.id = tbl.team_id
                GROUP BY t.id, t.name, t.schema_name
                ORDER BY t.id
            """)
            rows = cur.fetchall()
            
            headers = ["ID", "Team Name", "Schema Name", "Members", "Tables"]
            table_data = [[row[0], row[1], row[2], row[3], row[4]] for row in rows]
            
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        conn.close()
        
    except Exception as e:
        print(f"Error listing teams: {e}")

def list_users():
    """List all users in the database."""
    try:
        conn = connect_to_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.username, u.is_admin, 
                       string_agg(t.name, ', ') as teams
                FROM meta.users u
                LEFT JOIN meta.team_members tm ON u.id = tm.user_id
                LEFT JOIN meta.teams t ON tm.team_id = t.id
                GROUP BY u.id, u.username, u.is_admin
                ORDER BY u.id
            """)
            rows = cur.fetchall()
            
            headers = ["ID", "Username", "Admin", "Teams"]
            table_data = []
            
            for row in rows:
                user_id, username, is_admin, teams = row
                table_data.append([user_id, username, "Yes" if is_admin else "No", teams or "None"])
            
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        conn.close()
        
    except Exception as e:
        print(f"Error listing users: {e}")

def list_tables():
    """List all deployed tables."""
    try:
        conn = connect_to_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tbl.id, tbl.table_name, tbl.schema_name, t.name as team_name,
                       u.username as created_by, tbl.created_at, tbl.updated_at
                FROM meta.tables tbl
                JOIN meta.teams t ON tbl.team_id = t.id
                LEFT JOIN meta.users u ON tbl.created_by = u.id
                ORDER BY tbl.schema_name, tbl.table_name
            """)
            rows = cur.fetchall()
            
            headers = ["ID", "Table Name", "Schema", "Team", "Created By", "Created At", "Updated At"]
            table_data = []
            
            for row in rows:
                table_id, table_name, schema, team, creator, created_at, updated_at = row
                table_data.append([
                    table_id, table_name, schema, team, 
                    creator or "Unknown", 
                    created_at.strftime("%Y-%m-%d %H:%M") if created_at else "Unknown",
                    updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "Unknown"
                ])
            
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        conn.close()
        
    except Exception as e:
        print(f"Error listing tables: {e}")

def create_team(team_name):
    """Create a new team with its dedicated schema."""
    try:
        # Generate schema name (lowercase, no spaces)
        schema_name = f"team_{team_name.lower().replace(' ', '_')}"
        
        conn = connect_to_db()
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # Create team record
            cur.execute("""
                INSERT INTO meta.teams (name, schema_name)
                VALUES (%s, %s)
                RETURNING id;
            """, (team_name, schema_name))
            
            team_id = cur.fetchone()[0]
            
            # Create schema for the team
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
            
            # Create a role/group for the team
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'team_{schema_name}') THEN
                        CREATE ROLE team_{schema_name};
                    END IF;
                END
                $$;
            """)
            
            print(f"Team '{team_name}' created successfully with schema '{schema_name}'")
            print(f"Team ID: {team_id}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error creating team: {e}")

def create_user(username, password=None, is_admin=False, team=None):
    """Create a new database user."""
    if password is None:
        password = getpass.getpass(f"Enter password for user '{username}': ")
        confirm_password = getpass.getpass("Confirm password: ")
        
        if password != confirm_password:
            print("Error: Passwords do not match")
            return
    
    try:
        conn = connect_to_db()
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # Create database user
            pg_username = f"user_{username.lower().replace(' ', '_')}"
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = %s) THEN
                        CREATE USER {pg_username} WITH PASSWORD %s;
                    END IF;
                END
                $$;
            """, (pg_username, password))
            
            # Insert into users table
            cur.execute("""
                INSERT INTO meta.users (username, password_hash, is_admin)
                VALUES (%s, crypt(%s, gen_salt('bf')), %s)
                RETURNING id;
            """, (username, password, is_admin))
            
            user_id = cur.fetchone()[0]
            
            # If team is specified, add user to the team
            if team:
                # Check if team exists
                cur.execute("SELECT id, schema_name FROM meta.teams WHERE name = %s", (team,))
                team_result = cur.fetchone()
                
                if not team_result:
                    print(f"Warning: Team '{team}' not found. User created but not added to any team.")
                else:
                    team_id, schema_name = team_result
                    
                    # Add user to team in meta.team_members
                    cur.execute("""
                        INSERT INTO meta.team_members (user_id, team_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (user_id, team_id))
                    
                    # Grant team role to user
                    cur.execute(f"GRANT team_{schema_name} TO {pg_username};")
                    
                    # Grant usage on team schema
                    cur.execute(f"GRANT USAGE ON SCHEMA {schema_name} TO {pg_username};")
                    
                    # Grant usage on meta schema (for functions)
                    cur.execute(f"GRANT USAGE ON SCHEMA meta TO {pg_username};")
                    
                    print(f"User added to team '{team}'")
            
            # If admin, grant additional privileges
            if is_admin:
                cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {os.getenv('DB_DATABASE')} TO {pg_username};")
                cur.execute(f"GRANT ALL PRIVILEGES ON SCHEMA meta TO {pg_username};")
                cur.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA meta TO {pg_username};")
                cur.execute(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA meta TO {pg_username};")
                print("Admin privileges granted")
                
            # Create a user-specific .env file they can use
            with open(f"{username}.env", "w") as f:
                f.write(f"DB_HOST={os.getenv('DB_HOST')}\n")
                f.write(f"DB_PORT={os.getenv('DB_PORT', '5432')}\n")
                f.write(f"DB_USERNAME={pg_username}\n")
                f.write(f"DB_PASSWORD={password}\n")
                f.write(f"DB_DATABASE={os.getenv('DB_DATABASE')}\n")
                
                # If team was specified, add team info
                if team and team_result:
                    f.write(f"DB_TEAM_ID={team_result[0]}\n")
                    f.write(f"DB_TEAM_NAME={team}\n")
                    f.write(f"DB_SCHEMA={team_result[1]}\n")
            
            print(f"User '{username}' created successfully with PostgreSQL username '{pg_username}'")
            print(f"A connection file has been created at '{username}.env'")
            print(f"IMPORTANT: Share this file securely with the user")
        
        conn.close()
        
    except Exception as e:
        print(f"Error creating user: {e}")

def remove_user(username):
    """Remove a user from the database."""
    try:
        conn = connect_to_db()
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # Check if user exists
            cur.execute("SELECT id FROM meta.users WHERE username = %s", (username,))
            user_result = cur.fetchone()
            
            if not user_result:
                print(f"Error: User '{username}' not found.")
                conn.close()
                return
            
            user_id = user_result[0]
            
            # Get PostgreSQL username
            pg_username = f"user_{username.lower().replace(' ', '_')}"
            
            # Delete from meta.team_members (cascade will handle this)
            # Delete from meta.users
            cur.execute("DELETE FROM meta.users WHERE id = %s", (user_id,))
            
            # Drop PostgreSQL user
            cur.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = %s) THEN
                        DROP OWNED BY {pg_username};
                        DROP USER {pg_username};
                    END IF;
                END
                $$;
            """, (pg_username,))
            
            print(f"User '{username}' removed successfully.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error removing user: {e}")

def add_user_to_team(username, team_name):
    """Add a user to a team."""
    try:
        conn = connect_to_db()
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # Check if user exists
            cur.execute("SELECT id FROM meta.users WHERE username = %s", (username,))
            user_result = cur.fetchone()
            
            if not user_result:
                print(f"Error: User '{username}' not found.")
                conn.close()
                return
            
            user_id = user_result[0]
            
            # Get PostgreSQL username
            pg_username = f"user_{username.lower().replace(' ', '_')}"
            
            # Check if team exists
            cur.execute("SELECT id, schema_name FROM meta.teams WHERE name = %s", (team_name,))
            team_result = cur.fetchone()
            
            if not team_result:
                print(f"Error: Team '{team_name}' not found.")
                conn.close()
                return
            
            team_id, schema_name = team_result
            
            # Add user to team in meta.team_members
            cur.execute("""
                INSERT INTO meta.team_members (user_id, team_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
            """, (user_id, team_id))
            
            result = cur.fetchone()
            
            if result:
                # Grant team role to user
                cur.execute(f"GRANT team_{schema_name} TO {pg_username};")
                
                # Grant usage on team schema
                cur.execute(f"GRANT USAGE ON SCHEMA {schema_name} TO {pg_username};")
                
                # Grant access to existing tables
                cur.execute(f"""
                    DO $$
                    DECLARE
                        obj record;
                    BEGIN
                        FOR obj IN SELECT tablename FROM pg_tables WHERE schemaname = '{schema_name}'
                        LOOP
                            EXECUTE 'GRANT ALL PRIVILEGES ON TABLE {schema_name}.' || obj.tablename || ' TO {pg_username}';
                        END LOOP;
                    END $$;
                """)
                
                print(f"User '{username}' added to team '{team_name}'")
            else:
                print(f"User '{username}' is already a member of team '{team_name}'")
        
        conn.close()
        
    except Exception as e:
        print(f"Error adding user to team: {e}")

def main():
    parser = argparse.ArgumentParser(description="EZPostgres Admin Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List teams command
    subparsers.add_parser("list-teams", help="List all teams")
    
    # List users command
    subparsers.add_parser("list-users", help="List all users")
    
    # List tables command
    subparsers.add_parser("list-tables", help="List all deployed tables")
    
    # Create team command
    create_team_parser = subparsers.add_parser("create-team", help="Create a new team")
    create_team_parser.add_argument("name", help="Name for the new team")
    
    # Create user command
    create_user_parser = subparsers.add_parser("create-user", help="Create a new user")
    create_user_parser.add_argument("username", help="Username for the new user")
    create_user_parser.add_argument("--team", help="Team to add the user to")
    create_user_parser.add_argument("--admin", action="store_true", help="Make the user an administrator")
    
    # Remove user command
    remove_user_parser = subparsers.add_parser("remove-user", help="Remove a user")
    remove_user_parser.add_argument("username", help="Username of the user to remove")
    
    # Add user to team command
    add_user_parser = subparsers.add_parser("add-user-to-team", help="Add a user to a team")
    add_user_parser.add_argument("username", help="Username of the user")
    add_user_parser.add_argument("team", help="Name of the team")
    
    args = parser.parse_args()
    
    if args.command == "list-teams":
        list_teams()
    elif args.command == "list-users":
        list_users()
    elif args.command == "list-tables":
        list_tables()
    elif args.command == "create-team":
        create_team(args.name)
    elif args.command == "create-user":
        create_user(args.username, is_admin=args.admin, team=args.team)
    elif args.command == "remove-user":
        remove_user(args.username)
    elif args.command == "add-user-to-team":
        add_user_to_team(args.username, args.team)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()