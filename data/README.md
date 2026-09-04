# Data workspace

Raw and processed observations are not committed to Git.

Expected layout:

```text
data/
  raw/{source_id}/{vintage_date}/
  processed/features/{model_version}/
  fixtures/
```

Every raw asset must be accompanied by source ID, retrieval time, content hash and applicable license metadata.

