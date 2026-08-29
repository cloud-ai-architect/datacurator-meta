###############################################################################
# Tests for retention policy.
###############################################################################

package datacurator.retention

# Enables the v1 keywords (if, in, contains) on OPA 0.59+, and is the
# default in OPA 1.x. Without it these files parse under v0 rules and
# every `test_x if { ... }` fails with "var cannot be used for rule name".
import rego.v1

test_raw_retention_30_days if {
  retention_days["raw_s3"] == 30
}

test_chunk_retention_90_days if {
  retention_days["chunk_metadata_dynamo"] == 90
}

test_is_expired_yes if {
  is_expired("raw_s3", 31)
}

test_is_expired_no if {
  not is_expired("raw_s3", 15)
}

test_should_delete_chunk_old if {
  should_delete_chunk(100)
}

test_should_not_delete_chunk_new if {
  not should_delete_chunk(5)
}
