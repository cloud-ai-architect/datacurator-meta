###############################################################################
# dev.tfvars - dev environment configuration
# -----------------------------------------------------------------------------
# Override defaults for the dev environment. All other variables use the
# defaults from variables.tf.
#
# This file IS committed (no secrets); secrets live in GitHub Actions.
###############################################################################

aws_region             = "ap-south-1"
environment            = "dev"
project_name           = "datacurator"
owner                  = "vijay"
cost_center            = "portfolio"
github_org             = "cloud-ai-architect"
github_repo            = "datacurator-meta"
bedrock_model_id       = "amazon.titan-embed-text-v2:0"
embedding_dimensions   = 1024
lambda_runtime         = "python3.12"
lambda_memory_mb       = 512
lambda_timeout_seconds = 300
enable_cloudfront      = true
log_retention_days     = 30
monthly_budget_usd     = 20
