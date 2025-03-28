# EZPostgres Administration Guide

This document covers day-to-day administration tasks for managing your EZPostgres central database system.

## Team Management

### Creating Teams

1. **Create a new team**:
   ```bash
   python scripts/manage-central.py create-team "Marketing"
   ```
   This will:
   - Create a new team record in the meta.teams table
   - Create a PostgreSQL schema for the team
   - Create a PostgreSQL role for team access

2. **List existing teams**:
   ```bash
   python scripts/manage-central.py list-teams
   ```

3. **Update team information**:
   ```bash
   python scripts/manage-central.py update-team 1 --name "Digital Marketing"
   ```

### Team Schema Management

1. **View tables in a team's schema**:
   ```bash
   python scripts/manage-central.py list-team-tables "Marketing"
   ```

2. **Backup a team's schema**:
   ```bash
   python scripts/manage-central.py backup-team "Marketing" --output marketing_backup.sql
   ```

## User Management

### Managing User Accounts

1. **Create a new user**:
   ```bash
   python scripts/manage-central.py create-user jane --team "Marketing"
   ```
   This will:
   - Create a PostgreSQL user
   - Create a user record in meta.users
   - Add the user to the specified team
   - Generate a `.env` file for the user

2. **List all users**:
   ```bash
   python scripts/manage-central.py list-users
   ```

3. **Add a user to a team**:
   ```bash
   python scripts/manage-central.py add-user-to-team jane "Engineering"
   ```

4. **Remove a user from a team**:
   ```bash
   python scripts/manage-central.py remove-user-from-team jane "Marketing"
   ```

5. **Delete a user**:
   ```bash
   python scripts/manage-central.py remove-user jane
   ```

### Managing Admin Users

1. **Create an admin user**:
   ```bash
   python scripts/manage-central.py create-user admin2 --admin
   ```

2. **Grant admin privileges to existing user**:
   ```bash
   python scripts/manage-central.py update-user jane --admin
   ```

3. **Revoke admin privileges**:
   ```bash
   python scripts/manage-central.py update-user jane --no-admin
   ```

## Table Management

### Monitoring Tables

1. **List all tables in the database**:
   ```bash
   python scripts/manage-central.py list-tables
   ```

2. **Get details about a specific table**:
   ```bash
   python scripts/manage-central.py table-info "Marketing" "campaigns"
   ```

3. **Find tables that match a pattern**:
   ```bash
   python scripts/manage-central.py search-tables "user%"
   ```

### Table Maintenance

1. **Optimize a table**:
   ```bash
   python scripts/manage-central.py optimize-table "Marketing" "campaigns"
   ```

2. **View table size and statistics**:
   ```bash
   python scripts/manage-central.py table-stats "Marketing" "campaigns"
   ```

## System Monitoring

### Performance Monitoring

1. **Generate a usage report**:
   ```bash
   python scripts/monitoring.py --format html --output report.html
   ```

2. **View active queries**:
   ```bash
   python scripts/monitoring.py --active-queries
   ```

3. **Check database size**:
   ```bash
   python scripts/monitoring.py --database-size
   ```

### System Maintenance

1. **Clean up inactive users**:
   ```bash
   python scripts/manage-central.py cleanup-inactive-users --days 90
   ```

2. **View recent activity logs**:
   ```bash
   python scripts/manage-central.py view-activity-log --limit 20
   ```

## Backup and Restore

### Manual Backups

1. **Full database backup**:
   ```bash
   python scripts/manage-central.py backup-all --output full_backup.sql
   ```

2. **Backup specific team data**:
   ```bash
   python scripts/manage-central.py backup-team "Marketing" --output marketing_backup.sql
   ```

3. **Schedule regular backups**:
   ```bash
   # Add to crontab
   0 0 * * * cd /path/to/ezpostgres_admin && python scripts/manage-central.py backup-all --output /backups/ezpostgres_$(date +\%Y\%m\%d).sql
   ```

### Restore Operations

1. **Restore from full backup**:
   ```bash
   python scripts/manage-central.py restore --input full_backup.sql
   ```

2. **Restore a specific team**:
   ```bash
   python scripts/manage-central.py restore-team "Marketing" --input marketing_backup.sql
   ```

## Azure Management

### Server Configuration

1. **Scale up PostgreSQL resources**:
   ```bash
   az postgres flexible-server update \
     --resource-group <RESOURCE_GROUP> \
     --name <SERVER_NAME> \
     --sku-name GP_Gen5_4 \
     --storage-size 256
   ```

2. **Configure firewall rules**:
   ```bash
   az postgres flexible-server firewall-rule create \
     --resource-group <RESOURCE_GROUP> \
     --name <SERVER_NAME> \
     --rule-name "AllowOffice" \
     --start-ip-address "203.0.113.0" \
     --end-ip-address "203.0.113.255"
   ```

3. **Enable high availability**:
   ```bash
   az postgres flexible-server update \
     --resource-group <RESOURCE_GROUP> \
     --name <SERVER_NAME> \
     --high-availability Enabled
   ```

### Monitoring in Azure

1. **Set up Azure alerts**:
   ```bash
   az monitor alert create \
     --resource-group <RESOURCE_GROUP> \
     --name "High CPU Alert" \
     --target <SERVER_RESOURCE_ID> \
     --condition "CPU percentage > 80% for 5 minutes"
   ```

2. **View PostgreSQL logs in Azure**:
   ```bash
   az postgres flexible-server logs list \
     --resource-group <RESOURCE_GROUP> \
     --name <SERVER_NAME>
   ```

## Troubleshooting

### Common Issues

1. **Connection problems**:
   - Check firewall rules
   - Verify SSL settings
   - Test connection with psql:
     ```bash
     psql "host=<DB_HOST> port=<DB_PORT> dbname=<DB_DATABASE> user=<DB_USERNAME> password=<DB_PASSWORD> sslmode=require"
     ```

2. **Permission errors**:
   - Verify user is in the correct team
   - Check PostgreSQL role memberships:
     ```sql
     SELECT rolname, member FROM pg_roles r JOIN pg_auth_members m ON r.oid = m.roleid JOIN pg_roles m_r ON m.member = m_r.oid;
     ```

3. **Table deployment failures**:
   - Check PostgreSQL logs
   - Verify user has correct permissions

### Performance Issues

1. **Slow queries**:
   - Identify problematic queries:
     ```bash
     python scripts/monitoring.py --slow-queries
     ```
   - Analyze query execution plans

2. **Database growth**:
   - Monitor table sizes:
     ```bash
     python scripts/monitoring.py --format csv --output sizes.csv
     ```
   - Consider table partitioning for large tables

## System Updates

1. **Updating PostgreSQL version**:
   ```bash
   az postgres flexible-server update \
     --resource-group <RESOURCE_GROUP> \
     --name <SERVER_NAME> \
     --version 14
   ```

2. **Updating EZPostgres admin scripts**:
   ```bash
   git pull
   python scripts/update-system.py
   ```

## License

MIT License