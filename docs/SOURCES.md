# Sources for the numbers used in Gilbreth

Every figure below was checked against the original document on 12 Oct 2026 (quote or table read directly).
Figures marked *own calculation* are derived from the cited inputs.

## How long manual analysis takes
| Figure | Value | Source |
|---|---|---|
| Our course project: bimanual chart of the 284-s LEGO video, by hand | ≈ 60 min, one person (≈ 13 min per minute of video) | Team estimate (the 3 h first reported included several people and disorganisation) |
| Analyst time to analyse 1 min of work | MTM-1 350 min · MTM-2 130 min · MTM-UAS 40 min · MTM-SAM 20 min | IMD-EWD, *Teaching MTM systems*, slide 13 — [PDF](https://www.asocmtmesp.com/wp-content/uploads/2020/08/Teaching_MTM_systems_content_en.pdf) |
| Annotating hand primitives in video, frame by frame | 79.8 min per minute of recording | Kaku et al., *StrokeRehab*, NeurIPS 2022 Datasets & Benchmarks, §2.5: "One minute of recording took on average 79.8 minutes to annotate." — [PDF](https://papers.neurips.cc/paper_files/paper/2022/file/0b11fce9fb449c4171dbec167bf63e12-Paper-Datasets_and_Benchmarks.pdf) |

These are related tasks, not the exact one: we found no published measurement of analyst time per minute of video for a
full four-symbol ILO bimanual chart.

## Improvement levers
| Lever | Figure | Source |
|---|---|---|
| Free the holding hand | A fixture cut a two-hand plug assembly from 106.84 s to 66.38 s (−38 %); "the use of one hand to hold the base for assembly took the longest time" | Sivaloganathan, *Teaching Engineering Process Management…*, ASEE Annual Conference, paper #20434, Table 5 — [PDF](https://peer.asee.org/teaching-engineering-process-management-to-graduate-students-in-an-engineering-management-program.pdf) |
| Bring materials closer (β, default 30 %) | MTM-1 reach, case B: 10 cm 6.3 · 20 cm 10.0 · 30 cm 12.8 · 40 cm 15.6 · 60 cm 21.2 TMU (1 TMU = 0.036 s). Halving 60→30 cm saves 39.6 % of that reach; 40→20 cm saves 35.9 % (*own calculation*) | IMD-EWD MTM-1 data card, slide 58 (same PDF as above) |
| Both hands idle (α, default 50 %) | Adjustable assumption; no general published percentage | — |

Each lever is an estimate for prioritising; the real saving is measured by filming again after the change.

## Labour cost (value calculator)
| Figure | Value | Source |
|---|---|---|
| US, manufacturing, production occupations: employer cost per hour worked | USD 39.25 (June 2026) | BLS, *Employer Costs for Employee Compensation*, Table 4 — [link](https://www.bls.gov/news.release/ecec.t04.htm) |
| US, industrial engineers: mean wage | USD 52.84/h · USD 109,900/yr (May 2025) | BLS OEWS release USDL-26-0725 — [PDF](https://www.bls.gov/news.release/archives/ocwage_05152026.pdf) |
| Colombia, 2026 minimum monthly wage | COP 1,750,905, set *transitionally* by Decree 159 of 19 Feb 2026 pending a Consejo de Estado ruling | [Decree 0159 of 2026, art. 1](https://cancilleria.gov.co/normograma/compilacion/docs/decreto_0159_2026.htm) |
| Colombia, minimum-wage operator: employer cost per scheduled hour | COP 14,921–16,839 (*own calculation*: wage + transport allowance COP 249,095 + severance, interest, bonus, vacation, pension 12 %, family fund 4 %, ARL 0.522–6.96 %, ± health/SENA/ICBF 13.5 % if not exempt; ÷ 182 h/month for a 42-h week) | Decree 1470 of 2025 (transport allowance); MinSalud and UGPP contribution rates; Law 2101 of 2021 (42-h week from 15 Jul 2026) |

## Market
| Product | Published price | Source |
|---|---|---|
| MTM TiCon for Web (MTM-UAS modelling, manual) | EUR 1,490 per licence per year | [MTM Solutions catalogue](https://solutions.mtm.org/en-US) |
| MTM-Easy | EUR 990 per licence per year | same |
| TiConaut (proposes initial MTM data from video, approved by a person) | add-on to TiCon | same |

We did not find a commercial product documented to turn ordinary video, without markers or manual segmentation,
into the full four-symbol ILO bimanual chart. Not finding it does not prove it does not exist.
