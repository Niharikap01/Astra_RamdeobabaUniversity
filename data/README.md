# Synthetic data files

This directory contains generated data only:

- data/raw/patients.parquet
- data/raw/records_daily.parquet
- data/processed/features_all.parquet
- data/processed/train.parquet
- data/processed/val.parquet
- data/processed/test.parquet

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms. Model results therefore measure recovery of the simulator's assumptions and are not evidence on real patients.
