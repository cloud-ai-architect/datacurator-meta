###############################################################################
# IAM roles and policies.
# - GitHub Actions OIDC deploy role
# - Per-Lambda execution role (shared across all 9 lambdas)
# - Vectors role (for the S3 Vectors service)
#
# All permissions scoped to `Project=<project_name>` resource tag (where
# applicable) or specific resource ARNs.
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

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "github_subs" {
  type = list(string)
}

variable "github_org" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "github_aud" {
  type = string
}

variable "github_thumbprint" {
  type = string
}

variable "buckets" {
  type = map(string)
}

variable "tables" {
  type = map(string)
}

variable "lambdas" {
  type = map(string)
}

variable "vector_index_name" {
  type = string
}

variable "oidc_provider_arn" {
  type = string
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

# --- GitHub Actions deploy role (OIDC) ---

data "aws_iam_policy_document" "github_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = [var.github_aud]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = var.github_subs
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.name_prefix}-github-deploy-role"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
  tags               = var.common_tags
}

data "aws_iam_policy_document" "github_actions_inline" {
  statement {
    sid    = "AllActionsOnDatacurator"
    effect = "Allow"
    actions = [
      "*",
    ]
    resources = [
      "*",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = [var.project_name]
    }
  }
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "${var.project_name}-deploy-permissions"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_inline.json
}

# --- Per-Lambda execution role (shared by all 9 lambdas) ---

resource "aws_iam_role" "lambda_exec" {
  name = "${var.name_prefix}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.common_tags
}

data "aws_iam_policy_document" "lambda_basic" {
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "arn:aws:logs:*:*:log-group:/aws/lambda/${var.name_prefix}-*:*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_basic" {
  name   = "basic-execution"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_basic.json
}

data "aws_iam_policy_document" "lambda_s3_read" {
  statement {
    sid    = "ReadRawBucket"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:HeadObject",
      "s3:ListBucket",
    ]

    resources = [
      "arn:aws:s3:::${var.buckets.raw}",
      "arn:aws:s3:::${var.buckets.raw}/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_s3_read" {
  name   = "s3-read-raw"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_s3_read.json
}

data "aws_iam_policy_document" "lambda_bedrock" {
  statement {
    sid    = "BedrockInvoke"
    effect = "Allow"

    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    resources = [
      "arn:aws:bedrock:*:*:foundation-model/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_bedrock.json
}

data "aws_iam_policy_document" "lambda_dynamodb" {
  statement {
    sid    = "DynamoDBAccess"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
    ]

    resources = [
      "arn:aws:dynamodb:*:*:table/${var.tables.chunk_metadata}",
      "arn:aws:dynamodb:*:*:table/${var.tables.chunk_metadata}/index/*",
      "arn:aws:dynamodb:*:*:table/${var.tables.feedback}",
      "arn:aws:dynamodb:*:*:table/${var.tables.feedback}/index/*",
      "arn:aws:dynamodb:*:*:table/${var.tables.jobs}",
      "arn:aws:dynamodb:*:*:table/${var.tables.jobs}/index/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name   = "dynamodb-access"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_dynamodb.json
}

# S3 Vectors access for the lambda execution role.
#
# A separate `vectors` role exists below for privilege separation, but nothing
# assumes it: BaseLambda builds a plain boto3 s3vectors client from the
# function's own credentials. The route stage therefore failed with
# AccessDenied on s3vectors:PutVectors. Granting the actions here, scoped to
# this project's vector bucket and index, is what actually makes routing work.
data "aws_iam_policy_document" "lambda_s3vectors" {
  statement {
    sid    = "VectorsDataPlane"
    effect = "Allow"

    actions = [
      "s3vectors:GetVectors",
      "s3vectors:PutVectors",
      "s3vectors:DeleteVectors",
      "s3vectors:ListVectors",
      "s3vectors:QueryVectors",
      "s3vectors:GetIndex",
      "s3vectors:ListIndexes",
      "s3vectors:GetVectorBucket",
    ]

    resources = [
      "arn:aws:s3vectors:*:*:bucket/${var.buckets.vectors}",
      "arn:aws:s3vectors:*:*:bucket/${var.buckets.vectors}/index/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_s3vectors" {
  name   = "s3vectors-access"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_s3vectors.json
}

# Vectors role (assumed by lambda exec role)
data "aws_iam_policy_document" "vectors_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.lambda_exec.arn]
    }
  }
}

resource "aws_iam_role" "vectors" {
  name               = "${var.name_prefix}-vectors-role"
  assume_role_policy = data.aws_iam_policy_document.vectors_assume.json
  tags               = var.common_tags
}

data "aws_iam_policy_document" "vectors_inline" {
  statement {
    sid    = "VectorsAccess"
    effect = "Allow"

    actions = [
      "s3vectors:GetVectors",
      "s3vectors:PutVectors",
      "s3vectors:DeleteVectors",
      "s3vectors:ListVectors",
      "s3vectors:QueryVectors",
    ]

    resources = [
      "*",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = [var.project_name]
    }
  }
}

resource "aws_iam_role_policy" "vectors" {
  name   = "vectors-access"
  role   = aws_iam_role.vectors.id
  policy = data.aws_iam_policy_document.vectors_inline.json
}

resource "aws_iam_role_policy" "lambda_assume_vectors" {
  name = "assume-vectors-role"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = aws_iam_role.vectors.arn
    }]
  })
}

# Step Function execution role
resource "aws_iam_role" "step_function_exec" {
  name = "${var.name_prefix}-step-function-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.common_tags
}

data "aws_iam_policy_document" "step_function" {
  statement {
    sid     = "InvokeLambdas"
    effect  = "Allow"
    actions = ["lambda:InvokeFunction"]

    resources = [
      "arn:aws:lambda:*:*:function:${var.name_prefix}-*",
    ]
  }
}

resource "aws_iam_role_policy" "step_function" {
  name   = "step-function"
  role   = aws_iam_role.step_function_exec.id
  policy = data.aws_iam_policy_document.step_function.json
}

# EventBridge role
resource "aws_iam_role" "eventbridge" {
  name = "${var.name_prefix}-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.common_tags
}

data "aws_iam_policy_document" "eventbridge" {
  statement {
    sid     = "StartStepFunction"
    effect  = "Allow"
    actions = ["states:StartExecution"]

    resources = [
      "arn:aws:states:*:*:stateMachine:${var.name_prefix}-*",
    ]
  }
}

resource "aws_iam_role_policy" "eventbridge" {
  name   = "eventbridge"
  role   = aws_iam_role.eventbridge.id
  policy = data.aws_iam_policy_document.eventbridge.json
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "lambda_role_arn" {
  value = aws_iam_role.lambda_exec.arn
}

output "lambda_role_arns" {
  value = { for k, v in var.lambdas : k => aws_iam_role.lambda_exec.arn }
}

output "vectors_role_arn" {
  value = aws_iam_role.vectors.arn
}

output "api_role_arn" {
  value = aws_iam_role.lambda_exec.arn
}

output "api_role_arns" {
  value = { for k, v in var.lambdas : k => aws_iam_role.lambda_exec.arn }
}

output "state_machine_role_arn" {
  value = aws_iam_role.step_function_exec.arn
}

output "eventbridge_role_arn" {
  value = aws_iam_role.eventbridge.arn
}
