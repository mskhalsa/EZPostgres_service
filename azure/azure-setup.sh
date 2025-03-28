#!/bin/bash

# Install Azure CLI if not already installed
# curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Variables (customize these)
RESOURCE_GROUP="ezpostgres-central-rg"
LOCATION="eastus"
SERVER_NAME="ezpostgres-central"
ADMIN_USER="pgadmin"
ADMIN_PASSWORD="REPLACE_WITH_COMPLEX_PASSWORD" # Use a secure password generator
DATABASE_NAME="ezpostgresdb"
SKU="GP_Gen5_4" # General Purpose, Gen 5, 4 cores (for production use)

# Create a resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create a PostgreSQL server (Flexible Server for production)
az postgres flexible-server create \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --location $LOCATION \
  --admin-user $ADMIN_USER \
  --admin-password $ADMIN_PASSWORD \
  --sku-name $SKU \
  --tier GeneralPurpose \
  --storage-size 128 \
  --version 14 \
  --high-availability Enabled \
  --backup-retention 7 \
  --database-name $DATABASE_NAME

# For a production environment, you would NOT want to allow all IPs
# Instead, use either a VNet integration or a more restricted IP range
az postgres flexible-server firewall-rule create \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --rule-name "AllowAll" \
  --start-ip-address "0.0.0.0" \
  --end-ip-address "255.255.255.255"

# Get the connection string for admin
echo "Admin Connection string:"
echo "postgresql://$ADMIN_USER:$ADMIN_PASSWORD@$SERVER_NAME.postgres.database.azure.com:5432/$DATABASE_NAME"

# Create admin .env file
cat > admin.env << EOF
DB_HOST=$SERVER_NAME.postgres.database.azure.com
DB_PORT=5432
DB_USERNAME=$ADMIN_USER
DB_PASSWORD=$ADMIN_PASSWORD
DB_DATABASE=$DATABASE_NAME
EOF

echo "Created admin.env with connection details"
echo "IMPORTANT: Keep this file secure and do not distribute it to users!"