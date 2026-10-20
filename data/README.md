# Data Files

This directory contains synthetic raw and processed data produced by the NightWatch simulation pipeline.

## Files

- `raw/patients.parquet` — synthetic patient profiles and baseline clinical values.
- `raw/records_daily.parquet` — daily simulated wearable, medication, and morning/evening cuff records.
- `processed/features_all.parquet` — engineered feature matrix with next-day episode labels.
- `processed/train.parquet` — patient-grouped training split.
- `processed/val.parquet` — patient-grouped validation split.
- `processed/test.parquet` — patient-grouped test split.

## Data Limitations

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.
