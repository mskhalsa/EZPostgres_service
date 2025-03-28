#!/usr/bin/env python3
"""
EZPostgres Monitoring Script
----------------------------
This script provides monitoring and reporting for the central EZPostgres database.
It generates usage reports by team and can alert on potential issues.
"""

import os
import sys
import argparse
import datetime
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from tabulate import tabulate
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Add parent directory to path to import from templates
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from admin.env
load_dotenv('../templates/admin.env')

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

def get_team_usage():
    """Get usage statistics by team."""
    try:
        conn = connect_to_db()
        with conn.cursor() as cur:
            # Get team statistics
            cur.execute("""
                SELECT 
                    t.id, 
                    t.name,
                    COUNT(DISTINCT tm.user_id) as user_count,
                    COUNT(DISTINCT tbl.id) as table_count,
                    SUM(pg_total_relation_size(quote_ident(tbl.schema_name) || '.' || quote_ident(tbl.table_name)))::bigint as total_size_bytes
                FROM meta.teams t
                LEFT JOIN meta.team_members tm ON t.id = tm.team_id
                LEFT JOIN meta.tables tbl ON t.id = tbl.team_id
                GROUP BY t.id, t.name
                ORDER BY t.name
            """)
            team_data = cur.fetchall()
            
            # Get top 5 largest tables
            cur.execute("""
                SELECT 
                    t.name as team_name,
                    tbl.table_name,
                    pg_size_pretty(pg_total_relation_size(quote_ident(tbl.schema_name) || '.' || quote_ident(tbl.table_name))) as table_size,
                    pg_total_relation_size(quote_ident(tbl.schema_name) || '.' || quote_ident(tbl.table_name))::bigint as size_bytes
                FROM meta.tables tbl
                JOIN meta.teams t ON tbl.team_id = t.id
                ORDER BY size_bytes DESC
                LIMIT 5;
            """)
            largest_tables = cur.fetchall()
            
            # Get most active users (based on table creation/modification)
            cur.execute("""
                SELECT 
                    u.username,
                    COUNT(tbl.id) as table_count,
                    MAX(tbl.updated_at) as last_activity
                FROM meta.users u
                JOIN meta.tables tbl ON u.id = tbl.created_by
                GROUP BY u.username
                ORDER BY table_count DESC, last_activity DESC
                LIMIT 5;
            """)
            active_users = cur.fetchall()
        
        conn.close()
        
        return {
            "team_data": team_data,
            "largest_tables": largest_tables,
            "active_users": active_users
        }
        
    except Exception as e:
        print(f"Error getting team usage: {e}")
        return None

def get_system_stats():
    """Get system-wide statistics."""
    try:
        conn = connect_to_db()
        with conn.cursor() as cur:
            # Database size
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            db_size = cur.fetchone()[0]
            
            # Total number of tables
            cur.execute("SELECT COUNT(*) FROM meta.tables")
            table_count = cur.fetchone()[0]
            
            # Total number of teams
            cur.execute("SELECT COUNT(*) FROM meta.teams")
            team_count = cur.fetchone()[0]
            
            # Total number of users
            cur.execute("SELECT COUNT(*) FROM meta.users")
            user_count = cur.fetchone()[0]
            
            # Check for unused accounts (no activity in 30 days)
            cur.execute("""
                SELECT COUNT(*) 
                FROM meta.users u
                LEFT JOIN meta.tables tbl ON u.id = tbl.created_by
                WHERE u.is_admin = false
                GROUP BY u.id
                HAVING MAX(tbl.updated_at) < NOW() - INTERVAL '30 days' OR MAX(tbl.updated_at) IS NULL
            """)
            inactive_users = cur.fetchone()
            inactive_users = inactive_users[0] if inactive_users else 0
            
        conn.close()
        
        return {
            "db_size": db_size,
            "table_count": table_count,
            "team_count": team_count,
            "user_count": user_count,
            "inactive_users": inactive_users
        }
        
    except Exception as e:
        print(f"Error getting system stats: {e}")
        return None

def generate_usage_report(output_format="text", output_file=None):
    """Generate a usage report."""
    # Get usage data
    usage_data = get_team_usage()
    system_stats = get_system_stats()
    
    if not usage_data or not system_stats:
        print("Error: Failed to retrieve usage data.")
        return False
    
    # Format report data
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if output_format == "text":
        # Build text report
        report = [
            f"EZPostgres Usage Report - {timestamp}",
            "=" * 50,
            f"\nSystem Statistics:",
            f"  Database Size: {system_stats['db_size']}",
            f"  Total Tables: {system_stats['table_count']}",
            f"  Total Teams: {system_stats['team_count']}",
            f"  Total Users: {system_stats['user_count']}",
            f"  Inactive Users: {system_stats['inactive_users']}",
            
            "\nTeam Statistics:",
            tabulate(
                [[t[1], t[2], t[3], format_size(t[4])] for t in usage_data["team_data"]], 
                headers=["Team", "Users", "Tables", "Storage Used"]
            ),
            
            "\nLargest Tables:",
            tabulate(
                [[t[0], t[1], t[2]] for t in usage_data["largest_tables"]], 
                headers=["Team", "Table", "Size"]
            ),
            
            "\nMost Active Users:",
            tabulate(
                [[u[0], u[1], u[2].strftime("%Y-%m-%d %H:%M")] for u in usage_data["active_users"]], 
                headers=["Username", "Tables Created", "Last Activity"]
            )
        ]
        
        report_text = "\n".join(report)
        
        # Output report
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            print(f"Report saved to {output_file}")
        else:
            print(report_text)
            
    elif output_format == "html":
        # Build HTML report
        html_report = f"""
        <html>
        <head>
            <title>EZPostgres Usage Report - {timestamp}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1, h2 {{ color: #336791; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #336791; color: white; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .summary {{ display: flex; flex-wrap: wrap; }}
                .stat-box {{ background-color: #f8f9fa; border-radius: 5px; 
                           padding: 15px; margin: 10px; min-width: 150px; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #336791; }}
                .stat-label {{ font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <h1>EZPostgres Usage Report</h1>
            <p>Generated on {timestamp}</p>
            
            <h2>System Summary</h2>
            <div class="summary">
                <div class="stat-box">
                    <div class="stat-value">{system_stats['db_size']}</div>
                    <div class="stat-label">Database Size</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{system_stats['table_count']}</div>
                    <div class="stat-label">Total Tables</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{system_stats['team_count']}</div>
                    <div class="stat-label">Teams</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{system_stats['user_count']}</div>
                    <div class="stat-label">Users</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{system_stats['inactive_users']}</div>
                    <div class="stat-label">Inactive Users</div>
                </div>
            </div>
            
            <h2>Team Statistics</h2>
            <table>
                <tr>
                    <th>Team</th>
                    <th>Users</th>
                    <th>Tables</th>
                    <th>Storage Used</th>
                </tr>
        """
        
        for team in usage_data["team_data"]:
            html_report += f"""
                <tr>
                    <td>{team[1]}</td>
                    <td>{team[2]}</td>
                    <td>{team[3]}</td>
                    <td>{format_size(team[4])}</td>
                </tr>
            """
            
        html_report += """
            </table>
            
            <h2>Largest Tables</h2>
            <table>
                <tr>
                    <th>Team</th>
                    <th>Table</th>
                    <th>Size</th>
                </tr>
        """
        
        for table in usage_data["largest_tables"]:
            html_report += f"""
                <tr>
                    <td>{table[0]}</td>
                    <td>{table[1]}</td>
                    <td>{table[2]}</td>
                </tr>
            """
            
        html_report += """
            </table>
            
            <h2>Most Active Users</h2>
            <table>
                <tr>
                    <th>Username</th>
                    <th>Tables Created</th>
                    <th>Last Activity</th>
                </tr>
        """
        
        for user in usage_data["active_users"]:
            html_report += f"""
                <tr>
                    <td>{user[0]}</td>
                    <td>{user[1]}</td>
                    <td>{user[2].strftime("%Y-%m-%d %H:%M")}</td>
                </tr>
            """
            
        html_report += """
            </table>
        </body>
        </html>
        """
        
        # Output report
        if output_file:
            with open(output_file, 'w') as f:
                f.write(html_report)
            print(f"HTML report saved to {output_file}")
        else:
            print("HTML report generated (not displayed due to format)")
    
    elif output_format == "csv":
        # Create dataframes for each section
        team_df = pd.DataFrame(
            [[t[1], t[2], t[3], t[4]] for t in usage_data["team_data"]],
            columns=["Team", "Users", "Tables", "Storage_Bytes"]
        )
        
        tables_df = pd.DataFrame(
            [[t[0], t[1], t[2], t[3]] for t in usage_data["largest_tables"]],
            columns=["Team", "Table", "Size_Pretty", "Size_Bytes"]
        )
        
        users_df = pd.DataFrame(
            [[u[0], u[1], u[2]] for u in usage_data["active_users"]],
            columns=["Username", "Tables_Created", "Last_Activity"]
        )
        
        # Output to CSV
        if output_file:
            base_name = os.path.splitext(output_file)[0]
            team_df.to_csv(f"{base_name}_teams.csv", index=False)
            tables_df.to_csv(f"{base_name}_tables.csv", index=False)
            users_df.to_csv(f"{base_name}_users.csv", index=False)
            print(f"CSV reports saved to {base_name}_*.csv")
        else:
            print("Teams data:")
            print(team_df.to_string())
            print("\nLargest tables:")
            print(tables_df.to_string())
            print("\nMost active users:")
            print(users_df.to_string())
    
    return True

def format_size(size_bytes):
    """Format bytes to human-readable size."""
    if size_bytes is None:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def send_report_email(recipients, report_path):
    """Send the report via email."""
    try:
        # Configure email settings from env variables
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SMTP_EMAIL")
        sender_password = os.getenv("SMTP_PASSWORD")
        
        if not sender_email or not sender_password:
            print("Error: Email credentials not found in environment variables.")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"EZPostgres Usage Report - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        
        # Add message body
        body = "Please find attached the latest EZPostgres database usage report."
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach the report file
        with open(report_path, "rb") as f:
            attachment = MIMEApplication(f.read(), Name=os.path.basename(report_path))
            attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(report_path)}"'
            msg.attach(attachment)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f"Report sent to {', '.join(recipients)}")
        return True
    
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="EZPostgres Monitoring Tool")
    parser.add_argument("--format", choices=["text", "html", "csv"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--email", nargs="+", help="Email addresses to send the report to")
    
    args = parser.parse_args()
    
    # Generate the report
    if args.output:
        success = generate_usage_report(args.format, args.output)
    else:
        success = generate_usage_report(args.format)
    
    if success and args.email and args.output:
        send_report_email(args.email, args.output)

if __name__ == "__main__":
    main()