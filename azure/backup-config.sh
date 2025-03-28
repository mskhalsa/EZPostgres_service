#!/bin/bash

# Azure PostgreSQL Backup Configuration Script
# This script configures automated backups for the EZPostgres central database

# Load variables from admin.env
source ../templates/admin.env

# Variables
RESOURCE_GROUP=$(grep RESOURCE_GROUP admin.env | cut -d '=' -f2)
SERVER_NAME=$(grep SERVER_NAME admin.env | cut -d '=' -f2)

echo "Configuring backups for PostgreSQL server: $SERVER_NAME"

# Configure server backup retention period (7-35 days)
az postgres flexible-server update \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --backup-retention $BACKUP_RETENTION_DAYS

# Configure geo-redundant backup storage
az postgres flexible-server update \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --geo-redundant-backup $GEO_REDUNDANT_BACKUP

# Set up scheduled full backups
# Note: Azure Flexible Server automatically creates daily backups
# This just configures the retention and redundancy

echo "Configuring PostgreSQL point-in-time restore settings"
az postgres flexible-server update \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --tier $SERVER_TIER

echo "Backup configuration completed"
echo "Automated backups will be retained for $BACKUP_RETENTION_DAYS days"
if [ "$GEO_REDUNDANT_BACKUP" = "Enabled" ]; then
  echo "Geo-redundant backup storage is enabled"
else
  echo "Geo-redundant backup storage is disabled"
fi

# Display current backup settings
echo -e "\nCurrent backup configuration:"
az postgres flexible-server show \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --query '{backupRetentionDays:backupRetentionDays, geoRedundantBackup:geoRedundantBackup}'

# Instructions for manual backup and restore
echo -e "\nTo perform a manual backup:"
echo "1. Use Azure Portal or run:"
echo "   az postgres flexible-server backup --resource-group $RESOURCE_GROUP --name $SERVER_NAME"
echo ""
echo "To restore from backup:"
echo "1. Use Azure Portal or run:"
echo "   az postgres flexible-server restore --resource-group $RESOURCE_GROUP --name $SERVER_NAME-restored --source-server $SERVER_NAME --restore-time \"2023-01-01T00:00:00Z\""