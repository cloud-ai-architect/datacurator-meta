###############################################################################
# DataCurator - Root Terraform Configuration
# -----------------------------------------------------------------------------
# Provisions the full DataCurator stack: S3 buckets, DynamoDB, Lambdas, Step
# Function, API Gateway, CloudFront, IAM, and Resource Group.
#
# Deploy:
#   terraform init -backend-config="bucket=datacurator-tfstate-dev" \
#                   -backend-config="region=ap-south-1" \
#                   -backend-config="dynamodb_table=datacurator-tfstate-lock-dev"
#   terraform plan -var-file=envs/dev.tfvars
#   terraform apply -var-file=envs/dev.tfvars
#
# See: docs/runbooks/deploy.md
###############################################################################

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.62"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Backend is configured via -backend-config flags; see scripts/bootstrap.sh
  backend "s3" {
    # bucket         = "datacurator-tfstate-${var.environment}"
    # key            = "${var.environment}/terraform.tfstate"
    # region         = var.aws_region
    # dynamodb_table = "datacurator-tfstate-lock-${var.environment}"
    # encrypt        = true
    # kms_key_id     = "alias/terraform-state"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

provider "archive" {}

provider "random" {}
