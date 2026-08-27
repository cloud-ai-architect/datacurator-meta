###############################################################################
# S3 Vectors bucket and index.
# Vectors stored in a dedicated S3 bucket with S3 Vectors index.
# Encryption at rest with KMS (CMK).
###############################################################################

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "bucket_name"    { type = string }
variable "index_name"     { type = string }
variable "embedding_dim"  { type = number; default = 1024 }
variable "common_tags"    { type = map(string); default = {} }
variable "vectors_role_arn" { type = string }

# KMS key for vector bucket encryption
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

# S3 bucket that will hold the S3 Vectors index
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
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3vectors_vector_bucket" "this" {
  vector_bucket_name = var.bucket_name
  tags               = var.common_tags
}

resource "aws_s3vectors_index" "this" {
  vector_bucket_name = aws_s3vectors_vector_bucket.this.vector_bucket_name
  index_name         = var.index_name
  dimension          = var.embedding_dim
  distance_metric    = "cosine"
  tags               = var.common_tags
  depends_on = [aws_s3vectors_vector_bucket.this]
}

output "bucket_arn"      { value = aws_s3_bucket.this.arn }
output "bucket_name"     { value = aws_s3_bucket.this.bucket }
output "vector_bucket"   { value = aws_s3vectors_vector_bucket.this.vector_bucket_name }
output "index_arn"       { value = aws_s3vectors_index.this.index_arn }
output "index_name"      { value = aws_s3vectors_index.this.index_name }
output "kms_key_arn"     { value = aws_kms_key.this.arn }
