###############################################################################
# Step Function - the pipeline orchestrator.
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

variable "state_machine_arn" {
  type = string
}

variable "lambda_arns" {
  type = map(string)
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

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
          ErrorEquals    = ["States.TaskFailed"]
          IntervalSeconds = 1
          MaxAttempts    = 3
          BackoffRate    = 2.0
        }]

        Catch = [{
          ErrorEquals = ["States.ALL"]
          ResultPath  = "$.error"
          Next       = "Failed"
        }]

        Next = "Parse"
      }
      Parse = {
        Type = "Pass"
        Parameters = {
          "job_id.$"            = "$.Payload.job_id"
          "source_bucket.$"     = "$.Payload.source_bucket"
          "source_key.$"        = "$.Payload.source_key"
          "detected_format.$"   = "$.Payload.detected_format"
          "detected_encoding.$" = "$.Payload.detected_encoding"
          "size_bytes.$"        = "$.Payload.size_bytes"
        }
        ResultPath = "$.parsed"
        Next = "ParseLambda"
      }
      ParseLambda = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"

        Parameters = {
          "FunctionName" = var.lambda_arns["parse"]
          "Payload.$"    = "$.parsed"
        }

        ResultPath = "$.parseResult"
        Retry = [{
          ErrorEquals    = ["States.TaskFailed"]
          IntervalSeconds = 1
          MaxAttempts    = 3
          BackoffRate    = 2.0
        }]

        Catch = [{
          ErrorEquals = ["States.ALL"]
          ResultPath  = "$.error"
          Next       = "Failed"
        }]

        Next = "ChunkLambda"
      }
      ChunkLambda = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"

        Parameters = {
          "FunctionName" = var.lambda_arns["chunk"]
          "Payload.$"    = "$.parseResult.Payload"
        }

        ResultPath = "$.chunkResult"
        Retry = [{
          ErrorEquals    = ["States.TaskFailed"]
          IntervalSeconds = 1
          MaxAttempts    = 3
          BackoffRate    = 2.0
        }]

        Catch = [{
          ErrorEquals = ["States.ALL"]
          ResultPath  = "$.error"
          Next       = "Failed"
        }]

        Next = "Chunk"
      }
      Chunk = {
        Type      = "Map"
        ItemsPath = "$.chunkResult.Payload.chunks"
        Parameters = {
          "chunk.$" = "$$.Map.Item.Value"
        }

        Iterator = {
          StartAt = "RedactChunk"
          States = {
            RedactChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"

              Parameters = {
                "FunctionName" = var.lambda_arns["redact"]
                "Payload.$"    = "$"
              }

              Retry = [{
                ErrorEquals    = ["States.TaskFailed"]
                IntervalSeconds = 1
                MaxAttempts    = 3
                BackoffRate    = 2.0
              }]

              Catch = [{
                ErrorEquals = ["States.ALL"]
                ResultPath  = "$.error"
                Next       = "ChunkFailed"
              }]

              Next = "EmbedChunk"
            }
            EmbedChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"

              Parameters = {
                "FunctionName" = var.lambda_arns["embed"]
                "Payload.$"    = "$"
              }

              Retry = [{
                ErrorEquals    = ["States.TaskFailed"]
                IntervalSeconds = 1
                MaxAttempts    = 3
                BackoffRate    = 2.0
              }]

              Catch = [{
                ErrorEquals = ["States.ALL"]
                ResultPath  = "$.error"
                Next       = "ChunkFailed"
              }]

              Next = "ClassifyChunk"
            }
            ClassifyChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"

              Parameters = {
                "FunctionName" = var.lambda_arns["classify"]
                "Payload.$"    = "$"
              }

              Retry = [{
                ErrorEquals    = ["States.TaskFailed"]
                IntervalSeconds = 1
                MaxAttempts    = 3
                BackoffRate    = 2.0
              }]

              Catch = [{
                ErrorEquals = ["States.ALL"]
                ResultPath  = "$.error"
                Next       = "ChunkFailed"
              }]

              Next = "RouteChunk"
            }
            RouteChunk = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"

              Parameters = {
                "FunctionName" = var.lambda_arns["route"]
                "Payload.$"    = "$"
              }

              Retry = [{
                ErrorEquals    = ["States.TaskFailed"]
                IntervalSeconds = 1
                MaxAttempts    = 3
                BackoffRate    = 2.0
              }]

              Catch = [{
                ErrorEquals = ["States.ALL"]
                ResultPath  = "$.error"
                Next       = "ChunkFailed"
              }]

              End = true
            }
            ChunkFailed = { Type = "Fail", Cause = "Pipeline stage failed" }
          }
        }

        ResultPath = null
        End        = true
      }
      Failed = { Type = "Fail", Cause = "Pipeline failed" }
    }
  })
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/vendedlogs/states/${var.name_prefix}-pipeline"
  retention_in_days = 30
  tags              = var.common_tags
}

resource "aws_sfn_state_machine" "this" {
  name     = "${var.name_prefix}-pipeline"
  role_arn = var.state_machine_arn

  definition = local.asl_definition

  # logging_configuration disabled (provider version compat)

  tracing_configuration {
    enabled = true
  }

  tags = var.common_tags
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.this.arn
}

output "state_machine_name" {
  value = aws_sfn_state_machine.this.name
}

