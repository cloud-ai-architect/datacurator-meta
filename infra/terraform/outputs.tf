###############################################################################
# Outputs - exposed after `terraform apply` for downstream consumption.
###############################################################################

output "raw_bucket" {
  description = "S3 bucket for raw ingest"
  value       = local.buckets.raw
}

output "vectors_bucket" {
  description = "S3 bucket for vectors"
  value       = local.buckets.vectors
}

output "ui_bucket" {
  description = "S3 bucket for KB UI static assets"
  value       = local.buckets.ui
}

output "vector_index" {
  description = "S3 Vectors index name"
  value       = local.vector_index_name
}

output "api_url" {
  description = "API Gateway base URL"
  value       = module.apigateway.api_url
}

output "ui_url" {
  description = "KB UI URL (CloudFront or S3 website endpoint)"
  value       = var.enable_cloudfront ? module.cloudfront.distribution_domain : "https://${local.buckets.ui}.s3-website.${var.aws_region}.amazonaws.com"
}

output "step_function_arn" {
  description = "Step Function state machine ARN"
  value       = module.step_function.state_machine_arn
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC"
  value       = module.iam.github_actions_role_arn
}

output "resource_group_arn" {
  description = "Resource Group ARN for this environment"
  value       = module.resource_group.arn
}
