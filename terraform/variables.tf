variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
}

variable "location" {
  description = "Azure region for project resources"
  type        = string
  default     = "West Europe"
}

variable "container_app_environment_name" {
  description = "Name of the Azure Container Apps Environment"
  type        = string
  default     = "job-tracker-env"
}

variable "container_app_name" {
  description = "Name of the Azure Container App"
  type        = string
  default     = "job-tracker-api"
}

variable "container_image" {
  description = "Container image used by the API"
  type        = string
  default     = "ghcr.io/tomaszmurach/job-application-tracker:latest"
}

variable "postgres_server_name" {
  description = "Name of the Azure PostgreSQL Flexible Server"
  type        = string
  default     = "job-tracker-postgres"
}

variable "postgres_database_name" {
  description = "Name of the application PostgreSQL database"
  type        = string
  default     = "jobtracker"
}

variable "postgres_admin_username" {
  description = "Administrator username for PostgreSQL"
  type        = string
  default     = "jobtrackeradmin"
}