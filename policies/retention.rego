###############################################################################
# DataCurator Data Retention Policy
# -----------------------------------------------------------------------------
# Defines how long different data types should be retained.
# Used by the S3 lifecycle rules and DynamoDB TTL.
###############################################################################

package datacurator.retention

import future.keywords.if

# Retention in days for each data type
retention_days := {
  "raw_s3": 30,
  "chunk_metadata_dynamo": 90,
  "feedback_dynamo": 365,
  "jobs_dynamo": 365,
  "cloudwatch_logs": 30,
  "embeddings_s3_vectors": 1825,  # 5 years for production, but configurable
}

# Check whether a given data type is past its retention period
is_expired(data_type, age_days) if {
  limit := retention_days[data_type]
  age_days > limit
}

# Should this chunk be deleted?
should_delete_chunk(chunk_age_days) if {
  is_expired("chunk_metadata_dynamo", chunk_age_days)
}

# Should this raw file be deleted?
should_delete_raw_file(file_age_days) if {
  is_expired("raw_s3", file_age_days)
}
