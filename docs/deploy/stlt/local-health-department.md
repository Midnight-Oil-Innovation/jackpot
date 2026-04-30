# Local health department deployment

## Who this is for

City and county health departments — large urban LHDs (often part of
the Big Cities Health Coalition: NYC, LA, Chicago, Houston, etc.) and
mid-size county health departments — that want pathogen-genomics
capability without going through the state's deployment.

The fit varies by LHD size:

- **Big Cities Health Coalition cities** with their own labs: usually
  **Scenario C** (multi-lab agency, even if it's only 2–3 sub-labs:
  the central city lab plus a partner academic lab plus a partner
  hospital lab).
- **Mid-size LHDs** with one public-health lab: **Scenario B** (single
  org on cloud).
- **Small LHDs** without their own lab, contracting with a reference
  lab: **Scenario A** (laptop) for the bioinformatics or just rely on
  the state deployment.

## Fit rationale

LHDs typically have:

- One central health-department lab (or zero — contracting out).
- 1–3 partner labs (academic, hospital, commercial reference).
- An IT department that may be small or shared with the city/county
  general-services department.
- Strong relationships with the state public-health-lab system and
  with CDC.
- Variable analytical capacity — large urban LHDs often have
  bioinformatics staff comparable to states; mid-size LHDs may have
  less than 0.5 FTE.

JACKPOT's value:

- Lets the LHD keep their own data without depending on the state's
  IT timeline.
- Provides the audit + access-control layer that city/county legal
  often requires.
- Path to federation if the LHD wants to peer with the state, with
  neighboring counties, or with a regional academic hub.

## Install steps

1. **Coordinate with your state public-health lab.** Many states have
   policies about LHD-level data systems. Make sure your deployment
   doesn't conflict with state-level reporting expectations. If your
   state runs JACKPOT, federation peering between the state instance
   and the LHD instance may be the cleanest pattern.

2. **Provision the cloud or workstation.** Same patterns as the
   state-health-department guide, scaled smaller.

3. **Run `jackpot init`** (forthcoming). Pick the appropriate
   scenario per the size guidance above.

4. **Configure NCBI / GISAID.** LHDs sometimes submit under their own
   BioProject, sometimes under the state's BioProject with a
   sub-account. JACKPOT supports either.

5. **Seed reportable-organisms.** LHD reportable lists are typically a
   subset of the state list. The default 62-value seed plus any
   city/county-specific additions is a good starting point.

6. **Set up partner-lab access.** If you're deploying Scenario C with
   academic and hospital partner labs, each gets its own `Lab` row
   and Lab Director. The state lab's reference samples can be
   ingested via the standard upload flow.

7. **Define your case-system integration approach.** Most LHDs
   integrate at the case-system level rather than the lab-system
   level. The pattern is: NBS or local equivalent holds the case;
   JACKPOT holds the sample; specimen-ID join.

## Governance and data handling

- **Sharing-level default:** PRIVATE.
- **Federation with state:** Common pattern. Configure the state's
  JACKPOT instance as a federation peer; set up reciprocal sharing
  on agreed sample categories.
- **Federation with academic peers:** Possible. Useful for outbreak
  investigations where the academic lab is contributing analysis
  capacity.
- **DLP gate:** ON.
- **Audit log retention:** 7 years (matches CLIA / city public-records
  retention requirements; check with your jurisdiction).

## Funding sources

| Source | Eligibility | Use | Fit |
|---|---|---|---|
| **ELC (LHDs that are direct grantees)** | Big Cities Health Coalition cities + a few large counties | Lab capacity | ✅ Direct fit |
| **PHIG (LHDs that are direct grantees)** | Direct-grantee LHDs | Infrastructure | ✅ Direct fit |
| **PHIG passed through state** | All LHDs | Infrastructure | ✅ Indirect fit (depends on state pass-through policy) |
| **PHEP** | All LHDs | Preparedness | ⚠️ Possible for response-readiness framing |
| **DMI cooperative agreements** | Direct-grantee LHDs | Data modernization | ✅ Direct fit when available |
| **City / county own funds** | Self | Anything appropriated | ✅ Common path for jurisdictions with budget flexibility |
| **Hospital / academic partner cost-sharing** | Multi-org Scenario C | Shared IT and bioinformatics costs | ✅ Common for academic partnerships |

## Workforce considerations

- **Bioinformatics staff:** 1–2 FTE for a Big Cities deployment, 0.25–
  0.5 FTE for a mid-size LHD.
- **IT operations:** 0.5–1 FTE typical. Often shared with the city/
  county general-services IT.
- **Coordination with the state lab:** 0.1–0.25 FTE liaison capacity
  is helpful, especially in the first year.

## Common pitfalls

- **Deploying without coordinating with the state public-health lab.**
  If your state's PHL has expectations about specimen reporting,
  parallel infrastructure can create friction. Talk first.
- **Underbuilding the partner-lab access model.** Big Cities Health
  Coalition deployments often need to support 5+ partner labs by year
  2; build the access model with that in mind even if you start with
  2.
- **Treating the LHD deployment as a "mini state."** Some patterns
  that work at state scale (federated peering with multiple
  out-of-state peers, regional reference-data hosting) don't fit at
  LHD scale. Stay focused on what your jurisdiction actually does.
- **Forgetting that city legal counsel reviews public-health data
  systems too.** The audit log + access-control layer + the
  governance/ documents in this monorepo are designed to make that
  review easier; do the review early, not as an afterthought.
