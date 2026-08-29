###############################################################################
# CloudFront distribution in front of the S3 UI bucket.
# Provides HTTPS, caching, and CORS handling.
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

variable "ui_bucket" {
  type = string
}

variable "api_url" {
  type = string
}

variable "enabled" {
  type    = bool
  default = true
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

resource "aws_cloudfront_origin_access_control" "this" {
  name                              = "${var.name_prefix}-oac"
  description                       = "OAC for ${var.ui_bucket}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = var.enabled
  comment             = "DataCurator KB UI"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  tags                = var.common_tags

  origin {
    # Regional endpoint: the global "<bucket>.s3.amazonaws.com" form can
    # redirect for non-us-east-1 buckets, which OAC signing does not follow.
    domain_name              = "${var.ui_bucket}.s3.ap-south-1.amazonaws.com"
    origin_id                = "S3-${var.ui_bucket}"
    origin_access_control_id = aws_cloudfront_origin_access_control.this.id

    # The site is published under the static/ prefix, but CloudFront asks the
    # origin for default_root_object at the root ("/index.html"). Without
    # this the distribution returned 403 for every request.
    origin_path = "/static"
  }

  default_cache_behavior {
    target_origin_id       = "S3-${var.ui_bucket}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# Grant this distribution — and only this distribution — read access to the
# UI bucket.
#
# The bucket previously carried a public-read policy on static/*, which made
# the OAC pointless: anyone could fetch objects directly from S3 and bypass
# CloudFront entirely. Scoping to the CloudFront service principal with a
# SourceArn condition is the actual OAC pattern, and it lets the bucket keep
# public access fully blocked.
#
# The policy lives here rather than in the ui-bucket module because it needs
# the distribution ARN, and putting it there would create a module cycle.
resource "aws_s3_bucket_policy" "oac_read" {
  bucket = var.ui_bucket

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontOACRead"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "arn:aws:s3:::${var.ui_bucket}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.this.arn
          }
        }
      }
    ]
  })
}

output "distribution_id" {
  value = aws_cloudfront_distribution.this.id
}

output "distribution_domain" {
  value = aws_cloudfront_distribution.this.domain_name
}
