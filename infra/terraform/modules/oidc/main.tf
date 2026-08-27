###############################################################################
# GitHub OIDC provider for AWS.
# Lets GitHub Actions assume roles without long-lived credentials.
# See ADR-0004.
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

variable "oidc_url" {
  type    = string
  default = "https://token.actions.githubusercontent.com"
}

variable "client_id" {
  type    = string
  default = "sts.amazonaws.com"
}

variable "thumbprint" {
  type    = string
  default = "6938fd4d98bab03faadb97b34396831e3780aea1"
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = var.oidc_url
  client_id_list  = [var.client_id]
  thumbprint_list = [var.thumbprint]
  tags            = var.common_tags
}

output "provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
