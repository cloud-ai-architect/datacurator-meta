###############################################################################
# Data sources - resolve at apply time, never hardcoded.
###############################################################################

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
