terraform {
  required_version = ">= 1.16.0"

  backend "azurerm" {
    use_cli              = true
    use_azuread_auth     = true
    storage_account_name = "jobtrackertfstate64178"
    container_name       = "tfstate"
    key                  = "job-application-tracker.terraform.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}

  resource_provider_registrations = "none"
}