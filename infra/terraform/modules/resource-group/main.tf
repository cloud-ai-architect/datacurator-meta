###############################################################################
# Resource Group for visibility
###############################################################################

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

resource "aws_resourcegroups_group" "this" {
  name        = "rg-${var.name_prefix}"
  description = "DataCurator ${var.environment} resources"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [
        { Key = "Project", Values = [var.name_prefix] },
        { Key = "Environment", Values = [var.environment] },
      ]
    })
  }

  tags = var.common_tags
}

output "arn" {
  value = aws_resourcegroups_group.this.arn
}

output "name" {
  value = aws_resourcegroups_group.this.name
}
