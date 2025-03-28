# EZPostgres (Serivce Repo for Backend management)

A utility tool for easy deployment of PostgreSQL tables to a central, team-isolated database.

## Overview

EZPostgres simplifies PostgreSQL table management by allowing users to:

1. Define tables using a simple YAML configuration
2. Deploy tables to a central PostgreSQL database in Azure
3. Maintain team isolation (users can only see their team's tables)
4. Support team collaboration with shared table access

## How It Works

### For Users

As a user of EZPostgres, you can:

1. Define your database tables in `config.yaml`
2. Use `deploy.py` to create those tables in the central database
3. Access only the tables that belong to your team

### For Administrators

As an administrator, you can:

1. Set up a central PostgreSQL database on Azure
2. Create teams with isolated schemas
3. Manage users and their team memberships
4. Monitor all deployed tables across teams

## User Instructions

### Prerequisites

1. Python 3.6 or newer
2. PostgreSQL client tools
3. A `.env` file provided by your administrator

### Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/ezpostgres
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Place the `.env` file provided by your administrator in the project root.

### Defining Tables

Edit the `config.yaml` file to define your tables:

```yaml
tables:
  - name: my_custom_table
    columns:
      - name: id
        type: SERIAL
        primary_key: true
      - name: name
        type: VARCHAR(100)
        not_null: true
      - name: data
        type: JSONB
        not_null: false
  
  - name: another_table
    columns:
      - name: id
        type: SERIAL
        primary_key: true
      - name: description
        type: TEXT
        not_null: true
```

### Deploying Tables

Deploy your tables to the database:

```bash
python deploy.py
```

### Viewing Your Tables

List all tables in your team's schema:

```bash
python deploy.py --list
```

## Administrator Instructions

### Initial Setup

1. Set up an Azure PostgreSQL Flexible Server:
   ```bash
   chmod +x azure-setup.sh
   ./azure-setup.sh
   ```

2. Initialize the database structure:
   ```bash
   python initialize-central-db.py
   ```

### Managing Teams and Users

Use the admin tool to manage teams and users:

```bash
# Create a new team
python manage-central.py create-team "Engineering"

# Create a new user and add them to a team
python manage-central.py create-user johnsmith --team "Engineering"

# Create an admin user
python manage-central.py create-user adminuser --admin

# List all teams
python manage-central.py list-teams

# List all users
python manage-central.py list-users

# List all deployed tables
python manage-central.py list-tables
```

### Security Considerations

1. **Secure Connection Files**:
   - Keep the `admin.env` file secure and never commit it to version control
   - Distribute user `.env` files securely (e.g., via encrypted email)

2. **Azure Network Security**:
   - Configure Azure firewall rules to restrict access
   - Consider using Private Link for production environments

3. **Regular Access Reviews**:
   - Periodically review user accounts and team memberships
   - Remove unused accounts promptly

## Configuration Reference

### Column Properties

| Property | Description | Example |
|----------|-------------|---------|
| name | Column name | `username` |
| type | PostgreSQL data type | `VARCHAR(50)` |
| not_null | Set NOT NULL constraint | `true` |
| primary_key | Set as PRIMARY KEY | `true` |
| unique | Set UNIQUE constraint | `true` |
| default | Set default value | `CURRENT_TIMESTAMP` |
