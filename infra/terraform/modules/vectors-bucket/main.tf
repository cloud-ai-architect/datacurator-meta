###############################################################################
# S3 Vectors bucket and index.
# Uses null_resource + local-exec because the AWS Terraform provider does not
# yet have native support for aws_s3vectors_* resource types.
# See ADR-0002 for rationale.
###############################################################################

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

variable "bucket_name" {
  type = string
}

variable "index_name" {
  type = string
}

variable "embedding_dim" {
  type    = number
  default = 1024
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

variable "vectors_role_arn" {
  type = string
}

# --- KMS key + S3 bucket (for the underlying storage) ---

resource "aws_kms_key" "this" {
  description             = "KMS key for ${var.bucket_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = var.common_tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.bucket_name}"
  target_key_id = aws_kms_key.this.key_id
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  tags   = var.common_tags
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

# --- S3 Vectors bucket and index (via local-exec because Terraform provider doesn't support yet) ---

resource "null_resource" "s3_vector_bucket" {
  triggers = {
    bucket_name   = var.bucket_name
    index_name    = var.index_name
    embedding_dim = var.embedding_dim
  }

  # Delegates to a Python helper rather than an inline shell heredoc. The
  # previous heredoc silently no-opped under Windows cmd.exe while still
  # reporting success, so the index was never created and the Route stage
  # failed at runtime with "The specified index could not be found".
  # The helper is idempotent and exits non-zero on real failure.
  provisioner "local-exec" {
    command = join(" ", [
      "python",
      "${path.module}/../../../../scripts/ensure_vector_index.py",
      "--bucket", var.bucket_name,
      "--index", var.index_name,
      "--dimension", tostring(var.embedding_dim),
      "--region", "ap-south-1",
    ])
  }
}

resource "null_resource" "s3_vector_index_tag" {
  triggers = {
    bucket_name = var.bucket_name
    index_name  = var.index_name
  }

  depends_on = [null_resource.s3_vector_bucket]
  # Tag step disabled (ARN format quirk in s3vectors CLI; tags optional)
}

data "aws_caller_identity" "current" {}

output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "bucket_name" {
  value = aws_s3_bucket.this.bucket
}

output "vector_bucket" {
  value = var.bucket_name
}

output "index_arn" {
  value = "arn:aws:s3vectors:ap-south-1:${data.aws_caller_identity.current.account_id}:bucket/${var.bucket_name}/index/${var.index_name}"
}

output "index_name" {
  value = var.index_name
}

output "kms_key_arn" {
  value = aws_kms_key.this.arn
}
