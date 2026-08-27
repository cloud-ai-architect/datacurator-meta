###############################################################################
# Data sources - resolve at apply time, never hardcoded.
###############################################################################

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# AMIs not needed (no EC2), but available if Phase 5 adds Fargate.
# data "aws_ssm_parameter" "latest_ami" {
#   name = "/aws/service/ecs/optimized-ami/amzn2-ami-hvm-x86_64-gp2/recommended/image_id"
# }
