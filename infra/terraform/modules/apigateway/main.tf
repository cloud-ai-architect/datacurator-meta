###############################################################################
# API Gateway - HTTP API for the KB UI
# - GET  /search   -> search-lambda
# - POST /feedback -> feedback-lambda
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

variable "search_lambda" {
  type = string
}

variable "feedback_lambda" {
  type = string
}

variable "common_tags" {
  type    = map(string)
  default = {}
}

variable "log_retention_days" {
  type    = number
  default = 14
}

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"
  description   = "DataCurator KB API"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Amz-Date", "X-Amz-Security-Token"]
    max_age       = 300
  }

  tags = var.common_tags
}

# Access logs for the API stage.
#
# Without these there is no record of who called the API, what they asked
# for, or what status came back -- Lambda logs only cover requests that
# reached a handler, so anything rejected at the API layer (bad route, CORS,
# throttle) leaves no trace at all. Retention is short because this is
# operational telemetry, not an audit record.
resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
  tags        = var.common_tags

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn

    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      integrationErr = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_apigatewayv2_integration" "search" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.search_lambda
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "search" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "GET /search"
  target    = "integrations/${aws_apigatewayv2_integration.search.id}"
}

resource "aws_apigatewayv2_integration" "feedback" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.feedback_lambda
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "feedback" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "POST /feedback"
  target    = "integrations/${aws_apigatewayv2_integration.feedback.id}"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.search.id}"
}

resource "aws_lambda_permission" "search" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.search_lambda
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_lambda_permission" "feedback" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.feedback_lambda
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "api_url" {
  value = aws_apigatewayv2_api.this.api_endpoint
}

output "stage_name" {
  value = aws_apigatewayv2_stage.this.name
}
