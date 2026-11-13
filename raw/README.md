# raw/

Original downloads. Most stay out of git because of their size (O*NET 31.0 files, the Economic Index release, the ESCO crosswalk); [SOURCES.md](../SOURCES.md) lists each with its URL so anyone can fetch it again, and the build scripts take their folder with `--raw`.

Two small inputs are committed, because "Update data" needs them in a fresh clone:

- `dosm/jmi_data_2026q2.xlsx`: DOSM's "Data JMI Q2 2026" workbook (online job ads by MASCO major group). Put each new quarter's workbook next to it as `jmi_data_<year>q<quarter>.xlsx` and add its release and download dates to `JMI_DATES` in `scripts/demand.py`; the newest file is read.
- `mycol/mycol_2024_2025.csv`: the 66 occupations of MyCOL 2024/2025, typed from the TalentCorp brochure; their ISCO-08 links are in `data/mycol_map.csv`.
