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

locals {
  database_url = "postgresql+asyncpg://${var.postgres_admin_username}:${urlencode(random_password.postgres_admin.result)}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.postgres_database_name}?ssl=require"
}

resource "azurerm_container_app" "api" {
  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  secret {
    name  = "database-url"
    value = local.database_url
  }

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
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }

      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        initial_delay           = 5
        interval_seconds        = 5
        timeout                 = 2
        failure_count_threshold = 48
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        initial_delay           = 10
        interval_seconds        = 10
        timeout                 = 2
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/ready"
        initial_delay           = 5
        interval_seconds        = 5
        timeout                 = 2
        failure_count_threshold = 3
        success_count_threshold = 1
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
  zone                  = "3"

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

resource "azurerm_postgresql_flexible_server_firewall_rule" "container_app" {
  name             = "allow-container-app"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "20.50.214.197"
  end_ip_address   = "20.50.214.197"
}

resource "azurerm_container_app_job" "database_migration" {
  name                         = "job-tracker-db-migration"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location

  replica_timeout_in_seconds = 300
  replica_retry_limit        = 1

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  secret {
    name  = "database-url"
    value = local.database_url
  }

  template {
    container {
      name   = "migration"
      image  = var.container_image
      cpu    = 0.25
      memory = "0.5Gi"

      command = ["alembic"]
      args    = ["upgrade", "head"]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
    }
  }

  tags = {
    project     = "job-application-tracker"
    environment = "learning"
    managed_by  = "terraform"
  }
}
