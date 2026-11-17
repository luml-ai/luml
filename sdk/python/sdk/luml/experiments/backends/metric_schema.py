"""Metric definitions of experiment schema revision 3, shared by its migration and the
metric store.

They are part of the stored format, which published snapshots and released readers rely
on: changing one needs a new schema revision and migration, never an edit here.
"""

BUCKET_MIN_LEVEL = 3
BUCKET_MAX_LEVEL = 12

NUMERIC_SQL = "typeof({0}) IN ('real', 'integer')"
# Summable values: far enough below the double maximum that no sum can overflow.
SUMMABLE_SQL = "typeof({0}) IN ('real', 'integer') AND {0} BETWEEN -1e290 AND 1e290"
