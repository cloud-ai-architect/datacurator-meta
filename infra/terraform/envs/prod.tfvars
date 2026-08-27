###############################################################################
# prod.tfvars - production environment configuration
# -----------------------------------------------------------------------------
# Note: this is a portfolio project; "prod" is for demos. Real production
# would have additional safeguards (multi-region, AWS Config rules, etc.)
###############################################################################

aws_region            = "ap-south-1"
environment           = "prod"
project_name          = "datacurator"
owner                 = "vijay"
cost_center           = "portfolio"
github_org            = "vijaymadhu"
github_repo           = "datacurator-meta"
bedrock_model_id      = "amazon.titan-embed-text-v2:0"
embedding_dimensions  = 1024
lambda_runtime        = "python3.12"
lambda_memory_mb      = 1024
lambda_timeout_seconds = 600
enable_cloudfront     = true
log_retention_days    = 90
monthly_budget_usd    = 100
