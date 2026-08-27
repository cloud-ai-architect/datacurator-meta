###############################################################################
# Locals - computed values used across modules.
###############################################################################

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = coalesce(var.aws_region, data.aws_region.current.name)
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }

  # GitHub OIDC trust subject
  github_sub_main   = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  github_sub_pr     = "repo:${var.github_org}/${var.github_repo}:pull_request"
  github_oidc_url   = "https://token.actions.githubusercontent.com"
  github_aud        = "sts.amazonaws.com"
  github_thumbprint = "6938fd4d98bab03faadb97b34396831e3780aea1"

  # Vector index
  vector_index_name = "${var.project_name}-chunks-v1"
}
