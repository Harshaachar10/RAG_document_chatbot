# UI requirements (synthetic demo)

## Payment compliance review · P-3301

**Record header**

- Stated NPI: `1848459461` (suspected mismatch — registry owner is the Houston dermatologist, not the Chicago oncology context on the payment)
- Name as written: Sarah Lee · oncology · Chicago, IL

**Ranked candidates (typical order by score)**

| Rank | Doctor | Registry NPI | NPI comparison subtext (stated `1848459461`) |
|------|--------|--------------|---------------------------------------------|
| 1 | Sarah Lee-Kim | `1848459463` | Stated NPI belongs to someone else |
| 2 | Sara Li | `1848459465` | Stated NPI belongs to someone else |
| 3 | Sarah Lee (Houston) | `1848459461` | Stated NPI is this doctor's NPI |

Other field subtexts (name, specialty, location) come from the identity pipeline and must stay aligned with CSV/NPPES rows.

**Registry layout (`01_nppes_reference.csv`)**

- Sarah Lee-Kim (Chicago, medical oncology): `1848459463`
- Sara Li (Chicago): `1848459465`
- Sarah Lee (Houston, dermatology): `1848459461`

`1848459463` and `1848459465` are listed in `DEMO_SYNTHETIC_NPIS` so they load from the synthetic registry like standard NPIs.
