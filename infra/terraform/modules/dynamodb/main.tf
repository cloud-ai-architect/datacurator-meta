###############################################################################
# DynamoDB tables.
# Three tables: chunk-metadata, feedback, jobs.
# PAY_PER_REQUEST billing, TTL enabled, encryption at rest, point-in-time
# recovery enabled.
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

variable "tables" {
  type = map(string)
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

# --- chunk-metadata ---

resource "aws_dynamodb_table" "chunk_metadata" {
  name         = var.tables.chunk_metadata
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chunk_id"
  tags         = var.common_tags

  attribute {
    name = "chunk_id"
    type = "S"
  }

  attribute {
    name = "source_key"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  attribute {
    name = "detected_format"
    type = "S"
  }

  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "chunk_index"
    type = "N"
  }

  global_secondary_index {
    name            = "source-index"
    hash_key        = "source_key"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "format-index"
    hash_key        = "detected_format"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "job-index"
    hash_key        = "job_id"
    range_key       = "chunk_index"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

# --- feedback ---

resource "aws_dynamodb_table" "feedback" {
  name         = var.tables.feedback
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "feedback_id"
  tags         = var.common_tags

  attribute {
    name = "feedback_id"
    type = "S"
  }

  attribute {
    name = "chunk_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "chunk-index"
    hash_key        = "chunk_id"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

# --- jobs ---

resource "aws_dynamodb_table" "jobs" {
  name         = var.tables.jobs
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"
  tags         = var.common_tags

  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "started_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "started_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

output "chunk_metadata_arn" {
  value = aws_dynamodb_table.chunk_metadata.arn
}

output "feedback_arn" {
  value = aws_dynamodb_table.feedback.arn
}

output "jobs_arn" {
  value = aws_dynamodb_table.jobs.arn
}
