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

  # GitHub OIDC trust subjects.
  #
  # This organisation has "include organisation and repository IDs in the
  # subject claim" enabled, so GitHub actually presents:
  #   repo:cloud-ai-architect@258468489/<repo>@<repo-id>:ref:refs/heads/main
  # The plain form never matched, which is why every CI deploy failed with
  # "Not authorized to perform sts:AssumeRoleWithWebIdentity".
  #
  # The "@*" wildcards cover only the numeric IDs, so the org and repository
  # names are still pinned exactly, and the policy keeps working whether or
  # not that org setting is enabled.
  #
  # The environment subject is required separately: a job that declares
  # `environment: dev` gets ":environment:dev" instead of the ref subject.
  github_sub_main = "repo:${var.github_org}@*/${var.github_repo}@*:ref:refs/heads/main"
  github_sub_pr   = "repo:${var.github_org}@*/${var.github_repo}@*:pull_request"
  github_sub_env  = "repo:${var.github_org}@*/${var.github_repo}@*:environment:*"

  # Plain (no-ID) forms, in case the org setting is turned off later.
  github_sub_main_plain = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  github_sub_pr_plain   = "repo:${var.github_org}/${var.github_repo}:pull_request"
  github_sub_env_plain  = "repo:${var.github_org}/${var.github_repo}:environment:*"
  github_oidc_url   = "https://token.actions.githubusercontent.com"
  github_aud        = "sts.amazonaws.com"
  github_thumbprint = "6938fd4d98bab03faadb97b34396831e3780aea1"

  # Vector index
  vector_index_name = "${var.project_name}-chunks-v1"
}
