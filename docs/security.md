# EZPostgres Security Guide

This document outlines security best practices for managing your EZPostgres centralized database system.

## Authentication Security

### Admin Credentials

1. **Change Default Passwords Immediately**
   - The initial setup creates an `admin` user with password `admin123`
   - Change this password immediately after installation:
     ```bash
     psql "host=<DB_HOST> port=<DB_PORT> dbname=<DB_DATABASE> user=<DB_USERNAME> password=<DB_PASSWORD> sslmode=require" -c "UPDATE meta.users SET password_hash = crypt('your_new_secure_password', gen_salt('bf')) WHERE username = 'admin';"
     ```

2. **Admin Account Management**
   - Create individual admin accounts for each administrator
   - Avoid sharing the default admin account
   - Use strong, unique passwords for all admin accounts

3. **Password Policy**
   - The system enforces password complexity requirements:
     - Minimum 8 characters
     - At least one uppercase letter
     - At least one lowercase letter
     - At least one digit
     - At least one special character

### User Authentication

1. **Secure Credential Distribution**
   - When creating user accounts, securely distribute their `.env` files
   - Consider using encrypted email or secure file sharing
   - Instruct users to change their passwords after first login

2. **Regular Access Reviews**
   - Periodically review the list of users and their team memberships
   - Remove users who no longer need access
   - Adjust team memberships as organizational roles change

## Network Security

### Azure Firewall Configuration

1. **Restrict IP Access**
   - By default, the setup allows connections from anywhere
   - Modify to restrict access to specific IP addresses:
     ```bash
     az postgres flexible-server firewall-rule delete \
       --resource-group <RESOURCE_GROUP> \
       --name <SERVER_NAME> \
       --rule-name "AllowAll"
     
     az postgres flexible-server firewall-rule create \
       --resource-group <RESOURCE_GROUP> \
       --name <SERVER_NAME> \
       --rule-name "OfficeNetwork" \
       --start-ip-address "203.0.113.0" \
       --end-ip-address "203.0.113.255"
     ```

2. **Use Private Link for Production**
   - For production environments, consider using Azure Private Link
   - This provides a private endpoint in your VNet for your PostgreSQL server
   - Setup instructions:
     ```bash
     # Create a virtual network
     az network vnet create \
       --resource-group <RESOURCE_GROUP> \
       --name ezpostgres-vnet \
       --address-prefix 10.0.0.0/16 \
       --subnet-name default \
       --subnet-prefix 10.0.0.0/24
     
     # Create a private endpoint
     az network private-endpoint create \
       --resource-group <RESOURCE_GROUP> \
       --name ezpostgres-endpoint \
       --vnet-name ezpostgres-vnet \
       --subnet default \
       --private-connection-resource-id $(az postgres flexible-server show --resource-group <RESOURCE_GROUP> --name <SERVER_NAME> --query id -o tsv) \
       --group-id postgresqlServer \
       --connection-name ezpostgresConnection
     ```

3. **SSL Enforcement**
   - Azure PostgreSQL enforces SSL connections by default
   - Always use `sslmode=require` in connection strings

## Data Security

### Team Isolation

1. **Schema-Based Isolation**
   - Each team's data is stored in a separate PostgreSQL schema
   - PostgreSQL roles enforce access control
   - Row-level security policies provide additional protection

2. **Least Privilege Principle**
   - Regular users only have access to their team's schema
   - Users cannot see or access data from other teams
   - Admin users are the only ones with cross-team access

### Security Policies

1. **Row-Level Security**
   - RLS policies are implemented on meta tables
   - These ensure users only see data relevant to their teams
   - Admins bypass RLS for management purposes

2. **Function Security**
   - Critical functions use `SECURITY DEFINER`
   - This ensures they run with the privileges of the function creator
   - Access is controlled through GRANT statements

## Monitoring and Auditing

### Activity Logging

1. **User Activity Tracking**
   - All significant actions are logged in `meta.activity_log`
   - This includes table creations, schema modifications, etc.
   - Activity can be reviewed using:
     ```bash
     python scripts/manage-central.py activity-log
     ```

2. **Login Monitoring**
   - Failed login attempts are tracked
   - Rate limiting is applied to prevent brute force attacks
   - Review connection attempts:
     ```sql
     SELECT * FROM meta.connection_attempts 
     WHERE success = FALSE 
     ORDER BY attempt_time DESC 
     LIMIT 10;
     ```

### Regular Audits

1. **Security Auditing**
   - Schedule regular security reviews
   - Check for unused accounts or excessive privileges
   - Review team memberships and access patterns

2. **Monitoring Reports**
   - Generate regular monitoring reports:
     ```bash
     python scripts/monitoring.py --format html --output security-audit.html
     ```
   - Review for unusual patterns or potential security issues

## Backup and Recovery

### Backup Security

1. **Backup Encryption**
   - Azure PostgreSQL backups are encrypted by default
   - Additional encryption can be configured for exported backups

2. **Secure Backup Access**
   - Limit who can access database backups
   - Store backup credentials securely

3. **Geo-Redundant Backups**
   - Configure geo-redundant backup storage for disaster recovery
   - This is set in the `azure/backup-config.sh` script

### Emergency Recovery

1. **Point-in-Time Recovery**
   - Azure PostgreSQL allows point-in-time recovery
   - This can be used in case of security incidents or data corruption
   - Recovery procedure:
     ```bash
     az postgres flexible-server restore \
       --resource-group <NEW_RESOURCE_GROUP> \
       --name <NEW_SERVER_NAME> \
       --source-server <SOURCE_SERVER_NAME> \
       --restore-time "2023-01-01T00:00:00Z"
     ```

## Security Incident Response

1. **Response Plan**
   - Develop a security incident response plan
   - Include steps for containment, eradication, and recovery
   - Define roles and responsibilities

2. **User Access Revocation**
   - In case of compromise, quickly revoke user access:
     ```bash
     python scripts/manage-central.py disable-user <username>
     ```

3. **Logging and Forensics**
   - Preserve logs for security analysis
   - Document all actions taken during incident response

## Compliance Considerations

1. **Data Privacy**
   - Implement appropriate controls for data privacy regulations
   - Consider data classification and handling requirements
   - Limit sensitive data collection to what's necessary

2. **Access Documentation**
   - Maintain documentation of who has access to what data
   - This aids in compliance reporting and audits

3. **Regular Updates**
   - Keep PostgreSQL and Azure services updated
   - Apply security patches promptly
   - Review security bulletins for PostgreSQL regularly

## License

MIT License