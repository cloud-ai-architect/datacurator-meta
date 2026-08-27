###############################################################################
# EventBridge - S3 ObjectCreated -> Step Function start
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

variable "bucket_name" {
  type = string
}

variable "state_machine_arn" {
  type = string
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

data "aws_iam_policy_document" "eb_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name_prefix}-eventbridge-sf-role"
  assume_role_policy = data.aws_iam_policy_document.eb_assume.json
  tags               = var.common_tags
}

data "aws_iam_policy_document" "this" {
  statement {
    sid     = "StartStateMachine"
    effect  = "Allow"
    actions = ["states:StartExecution"]

    resources = [
      var.state_machine_arn,
    ]
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "start-state-machine"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

resource "aws_cloudwatch_event_rule" "this" {
  name        = "${var.name_prefix}-s3-trigger"
  description = "Trigger Step Function on S3 ObjectCreated in ingests/ prefix"
  tags        = var.common_tags

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = { name = [var.bucket_name] }
      object = { key = [{ prefix = "ingests/" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "this" {
  rule     = aws_cloudwatch_event_rule.this.name
  arn      = var.state_machine_arn
  role_arn = aws_iam_role.this.arn
}

output "rule_arn" {
  value = aws_cloudwatch_event_rule.this.arn
}

output "rule_name" {
  value = aws_cloudwatch_event_rule.this.name
}
