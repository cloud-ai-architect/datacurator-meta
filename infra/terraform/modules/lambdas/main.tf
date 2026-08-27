###############################################################################
# Lambda functions - one per stage.
# Uses zip deployment; Layer for shared dependencies.
###############################################################################

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
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
}

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "lambdas" {
  type = map(string)
}

variable "lambda_runtime" {
  type    = string
  default = "python3.12"
}

variable "lambda_memory_mb" {
  type    = number
  default = 512
}

variable "lambda_timeout" {
  type    = number
  default = 300
}

variable "buckets" {
  type = map(string)
}

variable "tables" {
  type = map(string)
}

variable "vector_index_name" {
  type = string
}

variable "bedrock_model_id" {
  type = string
}

variable "lambda_role_arns" {
  type = map(string)
}

variable "api_role_arns" {
  type = map(string)
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

locals {
  common_env = {
    ENVIRONMENT      = var.environment
    PROJECT_NAME     = var.project_name
    VECTOR_BUCKET    = var.buckets.vectors
    VECTOR_INDEX     = var.vector_index_name
    METADATA_TABLE   = var.tables.chunk_metadata
    FEEDBACK_TABLE   = var.tables.feedback
    JOBS_TABLE       = var.tables.jobs
    BEDROCK_MODEL_ID = var.bedrock_model_id
    LOG_LEVEL        = "INFO"
  }

  # Python handler format: module_path.function_name (dots, not colons)
  stage_lambdas = {
    detect   = "src.lambdas.detect_handler.handler"
    parse    = "src.lambdas.parse_handler.handler"
    chunk    = "src.lambdas.chunk_handler.handler"
    redact   = "src.lambdas.redact_handler.handler"
    embed    = "src.lambdas.embed_handler.handler"
    classify = "src.lambdas.classify_handler.handler"
    route    = "src.lambdas.route_handler.handler"
    search   = "src.lambdas.search_handler.handler"
    feedback = "src.lambdas.feedback_handler.handler"
  }
}

# Placeholder source package (in real deploy, built from src/)
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/build/placeholder.zip"

  source {
    content  = <<EOF
import json
def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"message": "placeholder"})}
EOF
    filename = "handler.py"
  }
}

resource "aws_lambda_function" "this" {
  for_each = var.lambdas

  function_name = each.value
  role          = var.lambda_role_arns[each.key]
  handler       = lookup(local.stage_lambdas, each.key, "src.lambdas.detect_handler:handler")
  runtime       = var.lambda_runtime
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  environment {
    variables = local.common_env
  }

  tags = var.common_tags

  tracing_config {
    mode = "Active"
  }

  depends_on = [data.archive_file.placeholder]
}

resource "aws_cloudwatch_log_group" "this" {
  for_each = var.lambdas

  name              = "/aws/lambda/${each.value}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

output "function_arns" {
  value = { for k, fn in aws_lambda_function.this : k => fn.arn }
}

output "function_names" {
  value = { for k, fn in aws_lambda_function.this : k => fn.function_name }
}

output "state_machine_role_arn" {
  value = var.lambda_role_arns["route"]
}
