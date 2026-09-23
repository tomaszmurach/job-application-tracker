output "resource_group_name" {
  description = "Name of the created Resource Group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_id" {
  description = "Azure Resource ID of the Resource Group"
  value       = azurerm_resource_group.main.id
}

output "resource_group_location" {
  description = "Azure region of the Resource Group"
  value       = azurerm_resource_group.main.location
}

output "container_app_environment_id" {
  description = "ID of the Azure Container Apps Environment"
  value       = azurerm_container_app_environment.main.id
}

output "container_app_environment_domain" {
  description = "Default domain of the Azure Container Apps Environment"
  value       = azurerm_container_app_environment.main.default_domain
}

output "container_app_fqdn" {
  description = "Stable public ingress FQDN of the API Container App"
  value       = azurerm_container_app.api.ingress[0].fqdn
}
