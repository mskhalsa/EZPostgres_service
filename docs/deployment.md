# EZPostgres Deployment Guide

This document outlines the process for setting up the centralized EZPostgres service on Azure.

## Initial Deployment

### 1. Azure Prerequisites

Before deploying, ensure you have:

- Azure account with sufficient permissions
- Azure CLI installed and configured
- PostgreSQL client tools installed

### 2. Setting Up the Environment

1. Clone the ezpostgres_admin repository:
   ```bash
   git clone https://github.com/yourusername/ezpostgres_admin
   cd ezpostgres_admin
   ```

2. Create your admin.env file:
   ```bash
   cp templates/admin.env.template templates/admin.env
   ```

3. Edit the admin.env file with your preferred settings:
   ```bash
   nano templates/admin.env
   ```

### 3. Azure PostgreSQL Setup

1. Execute the Azure setup script:
   ```bash
   chmod +x azure/azure-setup.sh
   ./azure/azure-setup.sh
   ```

2. If you need to customize the setup:
   ```bash
   # Edit the script first
   nano azure/azure-setup.sh
   ```

3. Security considerations:
   - By default, the script creates a firewall rule to allow all IPs
   - For production, edit the script to restrict access to specific IPs
   - Consider using Azure Private Link instead

### 4. Database Initialization

1. Initialize the database structure:
   ```bash
   python scripts/initialize-central-db.py
   ```

2. If you prefer to run the SQL directly:
   ```bash
   psql "host=<DB_HOST> port=<DB_PORT> dbname=<DB_DATABASE> user=<DB_USERNAME> password=<DB_PASSWORD> sslmode=require" -f sql/init-meta-schema.sql
   psql "host=<DB_HOST> port=<DB_PORT> dbname=<DB_DATABASE> user=<DB_USERNAME> password=<DB_PASSWORD> sslmode=require" -f sql/security-policies.sql
   ```

3. Verify the initialization:
   ```bash
   psql "host=<DB_HOST> port=<DB_PORT> dbname=<DB_DATABASE> user=<DB_USERNAME> password=<DB_PASSWORD> sslmode=require" -c "SELECT * FROM meta.users;"
   ```

## Creating Teams and Users

### 1. Team Setup

1. Create a new team:
   ```bash
   python scripts/manage-central.py create-team "Engineering"
   ```

2. Verify team creation:
   ```bash
   python scripts/manage-central.py list-teams
   ```

### 2. User Management

1. Create a regular user and add them to a team:
   ```bash
   python scripts/manage-central.py create-user john --team "Engineering"
   ```

2. Create an admin user:
   ```bash
   python scripts/manage-central.py create-user admin2 --admin
   ```

3. Add an existing user to a team:
   ```bash
   python scripts/manage-central.py add-user-to-team jane "Finance"
   ```

4. Verify user creation:
   ```bash
   python scripts/manage-central.py list-users
   ```

5. Distributing user credentials:
   - The `create-user` command generates a `username.env` file
   - Send this file securely to the user
   - Instruct them to place it in their EZPostgres directory as `.env`

## Monitoring and Maintenance

### 1. Regular Monitoring

1. Generate usage reports:
   ```bash
   python scripts/monitoring.py --format html --output report.html
   ```

2. Set up scheduled monitoring:
   ```bash
   # Add to crontab
   0 0 * * * cd /path/to/ezpostgres_admin && python scripts/monitoring.py --format html --output reports/$(date +\%Y\%m\%d).html --email admin@example.com
   ```

### 2. Backup Configuration

1. Configure automated backups:
   ```bash
   chmod +x azure/backup-config.sh
   ./azure/backup-config.sh
   ```

2. Azure PostgreSQL Flexible Server provides automatic backups, but you can customize:
   - Retention period (7-35 days)
   - Geo-redundancy

### 3. Performance Optimization

1. Monitor database performance:
   ```bash
   python scripts/monitoring.py
   ```

2. Consider scaling the Azure PostgreSQL server if needed:
   ```bash
   az postgres flexible-server update \
     --resource-group <RESOURCE_GROUP> \
     --name <SERVER_NAME> \
     --sku-name GP_Gen5_4 \
     --storage-size 256
   ```

## Troubleshooting

### Common Issues

1. **Connection Issues**
   - Check firewall rules in Azure
   - Verify SSL requirements

2. **Permission Errors**
   - Make sure users are assigned to the correct teams
   - Verify PostgreSQL roles are correctly assigned

3. **Deployment Failures**
   - Check PostgreSQL logs
   - Verify user has permissions to their team's schema

### Getting Help

For additional assistance:
- Check Azure PostgreSQL documentation
- Review logs in Azure Portal
- Contact support if running into Azure-specific issues

## Upgrading

When upgrading the EZPostgres system:

1. Backup the database first
2. Update the admin repository
3. Apply any new SQL scripts
4. Update user repositories for compatibility

## License

MIT License