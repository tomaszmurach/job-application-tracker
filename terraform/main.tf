resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    project     = "job-application-tracker"
    environment = "learning"
    managed_by  = "terraform"
  }
}

resource "azurerm_container_app_environment" "main" {
  name                = var.container_app_environment_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  tags = {
    project     = "job-application-tracker"
    environment = "learning"
    managed_by  = "terraform"
  }
}

resource "azurerm_container_app" "api" {
  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  ingress {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8000
    transport                  = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "api"
      image  = var.container_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "DATABASE_URL"
        value = "sqlite+aiosqlite:///./jobtracker.db"
      }
    }
  }

  tags = {
    project     = "job-application-tracker"
    environment = "learning"
    managed_by  = "terraform"
  }
}

resource "random_password" "postgres_admin" {
  length           = 24
  special          = true
  override_special = "!#$%&*-_"

  min_upper   = 1
  min_lower   = 1
  min_numeric = 1
  min_special = 1
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                = var.postgres_server_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  version                = "17"
  administrator_login    = var.postgres_admin_username
  administrator_password = random_password.postgres_admin.result

  sku_name              = "B_Standard_B1ms"
  storage_mb            = 32768
  backup_retention_days = 7

  public_network_access_enabled = true

  tags = {
    project     = "job-application-tracker"
    environment = "learning"
    managed_by  = "terraform"
  }
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = var.postgres_database_name
  server_id = azurerm_postgresql_flexible_server.main.id

  charset   = "UTF8"
  collation = "en_US.utf8"
}