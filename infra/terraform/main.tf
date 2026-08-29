###############################################################################
# DataCurator - Main Terraform
# -----------------------------------------------------------------------------
# Composes all modules. Each module is single-purpose and can be re-used.
###############################################################################

locals {
  buckets = {
    raw     = "${local.name_prefix}-raw"
    vectors = "${local.name_prefix}-vectors"
    ui      = "${local.name_prefix}-ui"
  }

  tables = {
    chunk_metadata = "${local.name_prefix}-chunk-metadata"
    feedback       = "${local.name_prefix}-feedback"
    jobs           = "${local.name_prefix}-jobs"
  }

  lambdas = {
    detect   = "${local.name_prefix}-detect"
    parse    = "${local.name_prefix}-parse"
    chunk    = "${local.name_prefix}-chunk"
    redact   = "${local.name_prefix}-redact"
    embed    = "${local.name_prefix}-embed"
    classify = "${local.name_prefix}-classify"
    route    = "${local.name_prefix}-route"
    search   = "${local.name_prefix}-search"
    feedback = "${local.name_prefix}-feedback"
  }
}

# --- OIDC + IAM (foundation; everything else depends on this) ---

module "oidc" {
  source      = "./modules/oidc"
  oidc_url    = local.github_oidc_url
  client_id   = local.github_aud
  thumbprint  = local.github_thumbprint
  common_tags = local.common_tags
}

module "iam" {
  source = "./modules/iam"

  project_name      = var.project_name
  environment       = var.environment
  name_prefix       = local.name_prefix
  github_org        = var.github_org
  github_repo       = var.github_repo
  github_subs = [

    local.github_sub_main,

    local.github_sub_pr,

    local.github_sub_env,

    local.github_sub_main_plain,

    local.github_sub_pr_plain,

    local.github_sub_env_plain,

  ]
  github_aud        = local.github_aud
  github_thumbprint = local.github_thumbprint
  buckets           = local.buckets
  tables            = local.tables
  lambdas           = local.lambdas
  vector_index_name = local.vector_index_name
  oidc_provider_arn = module.oidc.provider_arn
  common_tags       = local.common_tags
}

# --- Storage ---

module "raw_bucket" {
  source = "./modules/raw-bucket"

  bucket_name = local.buckets.raw
  common_tags = local.common_tags
}

module "vectors_bucket" {
  source = "./modules/vectors-bucket"

  bucket_name      = local.buckets.vectors
  index_name       = local.vector_index_name
  embedding_dim    = var.embedding_dimensions
  common_tags      = local.common_tags
  vectors_role_arn = module.iam.vectors_role_arn
}

module "ui_bucket" {
  source = "./modules/ui-bucket"

  bucket_name = local.buckets.ui
  common_tags = local.common_tags
}

module "dynamodb" {
  source = "./modules/dynamodb"

  tables      = local.tables
  common_tags = local.common_tags
}

# --- Compute ---

module "lambdas" {
  source = "./modules/lambdas"

  project_name       = var.project_name
  environment        = var.environment
  name_prefix        = local.name_prefix
  lambdas            = local.lambdas
  lambda_runtime     = var.lambda_runtime
  lambda_memory_mb   = var.lambda_memory_mb
  lambda_timeout     = var.lambda_timeout_seconds
  buckets            = local.buckets
  tables             = local.tables
  vector_index_name  = local.vector_index_name
  bedrock_model_id   = var.bedrock_model_id
  lambda_role_arns   = module.iam.lambda_role_arns
  api_role_arns      = module.iam.api_role_arns
  log_retention_days = var.log_retention_days
  common_tags        = local.common_tags
}

module "step_function" {
  source = "./modules/step-function"

  name_prefix       = local.name_prefix
  state_machine_arn = module.iam.state_machine_role_arn
  lambda_arns       = module.lambdas.function_arns
  common_tags       = local.common_tags
}

module "eventbridge" {
  source = "./modules/eventbridge"

  name_prefix       = local.name_prefix
  bucket_name       = local.buckets.raw
  state_machine_arn = module.step_function.state_machine_arn
  common_tags       = local.common_tags
}

# --- API + UI ---

module "apigateway" {
  source = "./modules/apigateway"

  name_prefix     = local.name_prefix
  search_lambda   = module.lambdas.function_arns["search"]
  feedback_lambda = module.lambdas.function_arns["feedback"]
  common_tags     = local.common_tags
}

module "cloudfront" {
  source = "./modules/cloudfront"

  name_prefix = local.name_prefix
  ui_bucket   = local.buckets.ui
  api_url     = module.apigateway.api_url
  enabled     = var.enable_cloudfront
  common_tags = local.common_tags
}

# --- Resource Group for visibility ---

module "resource_group" {
  source = "./modules/resource-group"

  name_prefix = local.name_prefix
  environment = var.environment
  common_tags = local.common_tags
}
