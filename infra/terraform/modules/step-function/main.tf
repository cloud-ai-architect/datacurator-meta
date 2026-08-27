###############################################################################
# Step Function - the pipeline orchestrator.
# State machine in Amazon States Language (ASL).
# See docs/architecture/02-lld.md for the full state machine.
###############################################################################

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "name_prefix"        { type = string }
variable "state_machine_arn"  { type = string }
variable "lambda_arns"        { type = map(string) }
variable "common_tags"        { type = map(string); default = {} }

locals {
  asl_definition = jsonencode({
    Comment = "DataCurator ingestion pipeline (Phase 1)"
    StartAt = "Detect"
    States = {
      Detect = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          "FunctionName" = var.lambda_arns["detect"]
          "Payload.$"    = "$"
        }
        Retry = [{
          ErrorEquals = ["States.TaskFailed"]
          IntervalSeconds = 1
          MaxAttempts = 3
          BackoffRate = 2.0
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          ResultPath = "$.error"
          Next       = "Failed"
        }]
        Next = "Parse"
      }
      Parse = {
        Type = "Choice"
        Choices = [
          { Variable = "$.detected_format", StringEquals = "pdf",  Next = "ParsePdf" },
          { Variable = "$.detected_format", StringEquals = "csv",  Next = "ParseCsv" },
          { Variable = "$.detected_format", StringEquals = "json", Next = "ParseJson" },
          { Variable = "$.detected_format", StringEquals = "html", Next = "ParseHtml" },
        ]
        Default = "Failed"
      }
      ParsePdf = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = { "FunctionName" = var.lambda_arns["parse"], "Payload.$" = "$.Payload" }
        ResultPath = "$.parsed"
        Retry = [{ ErrorEquals = ["States.TaskFailed"], IntervalSeconds = 1, MaxAttempts = 3, BackoffRate = 2.0 }]
        Catch  = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Failed" }]
        Next = "Chunk"
      }
      ParseCsv  { Type = "Pass", Next = "Chunk" }
      ParseJson { Type = "Pass", Next = "Chunk" }
      ParseHtml { Type = "Pass", Next = "Chunk" }
      Chunk = {
        Type     = "Map"
        ItemsPath = "$.chunks"
        Parameters = { "chunk.$" = "$$.Map.Item.Value" }
        Iterator = {
          StartAt = "RedactChunk"
          States = {
            RedactChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = { "FunctionName" = var.lambda_arns["redact"], "Payload.$" = "$" }
              Retry = [{ ErrorEquals = ["States.TaskFailed"], IntervalSeconds = 1, MaxAttempts = 3, BackoffRate = 2.0 }]
              Catch  = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Failed" }]
              Next = "EmbedChunk"
            }
            EmbedChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = { "FunctionName" = var.lambda_arns["embed"], "Payload.$" = "$" }
              Retry = [{ ErrorEquals = ["States.TaskFailed"], IntervalSeconds = 1, MaxAttempts = 3, BackoffRate = 2.0 }]
              Catch  = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Failed" }]
              Next = "ClassifyChunk"
            }
            ClassifyChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = { "FunctionName" = var.lambda_arns["classify"], "Payload.$" = "$" }
              Retry = [{ ErrorEquals = ["States.TaskFailed"], IntervalSeconds = 1, MaxAttempts = 3, BackoffRate = 2.0 }]
              Catch  = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Failed" }]
              Next = "RouteChunk"
            }
            RouteChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = { "FunctionName" = var.lambda_arns["route"], "Payload.$" = "$" }
              Retry = [{ ErrorEquals = ["States.TaskFailed"], IntervalSeconds = 1, MaxAttempts = 3, BackoffRate = 2.0 }]
              Catch  = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Failed" }]
              End = true
            }
            Failed = { Type = "Fail", Cause = "Pipeline stage failed" }
          }
        }
        ResultPath = null
        End = true
      }
      Failed = { Type = "Fail", Cause = "Pipeline failed" }
    }
  })
}

resource "aws_sfn_state_machine" "this" {
  name     = "${var.name_prefix}-pipeline"
  role_arn = var.state_machine_arn

  definition = local.asl_definition

  logging_configuration {
    log_group_arn        = "${aws_cloudwatch_log_group.this.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tracing_configuration {
    enabled = true
  }

  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/vendedlogs/states/${var.name_prefix}-pipeline"
  retention_in_days = 30
  tags              = var.common_tags
}

output "state_machine_arn"  { value = aws_sfn_state_machine.this.arn }
output "state_machine_name" { value = aws_sfn_state_machine.this.name }
