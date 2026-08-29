###############################################################################
# S3 bucket for the KB UI (static website hosting).
# Private bucket. CloudFront reads it through Origin Access Control; there
# is no public access path.
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

variable "bucket_name" {
  type = string
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  tags   = var.common_tags
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls = true
  # Nothing here is public any more: CloudFront reads via OAC using the
  # bucket policy defined in the cloudfront module.
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_website_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "bucket_name" {
  value = aws_s3_bucket.this.bucket
}

output "website_endpoint" {
  value = aws_s3_bucket_website_configuration.this.website_endpoint
}

output "website_domain" {
  value = aws_s3_bucket_website_configuration.this.website_domain
}
