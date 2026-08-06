> **Status:** Reference — outstanding work on Level 1 federated query pagination.

# Federation L1 Query Pagination — Outstanding Work

**Document type:** Work-to-be-done record for the Level 1 query fan-out.
**Audience:** whoever picks up the federation pagination slice.
**Origin:** security/correctness review of `backend/`, August 2026. The envelope-key
half of these findings shipped in `545be64`; everything below is still open.

---

## 1. Why this document exists

`FederationClient` fans a query out to every enabled partner and merges the
results. Pagination was designed for — `DEFAULT_PER_PARTNER_PAGE_SIZE` is declared
at `backend/backend/federation/client.py:39` — but never wired. The client reads
whatever the partner returns in a single response and never looks at the
`pagination` block.

Fixing this in isolation is not possible: the parameter that would control page
size is one of several that the partner does not recognise. The pagination work
and the wire-contract work are the same task.

---

## 2. What is broken today

### 2.1 Pagination is never followed

`_query_one` (`client.py:146-189`) issues exactly one `GET` per partner and
returns its rows. The response envelope carries
`pagination: {page, per_page, total, pages}` (see `backend/backend/responses.py`
`success_list`), and none of it is read. A partner holding more than one page of
matching samples silently contributes only its first page.

`DEFAULT_PER_PARTNER_PAGE_SIZE = 50` at `client.py:39` is referenced nowhere.

### 2.2 The page-size parameter name does not match

`FederationQuery.page_size` (`backend/backend/federation/models.py:110`)
serialises as `page_size`. The samples list endpoint
(`backend/backend/routers/samples.py:213`) declares `per_page`. FastAPI drops
unrecognised query parameters silently, so the partner applies its own default
page size and the caller's value has no effect.

`page` is the one pagination parameter that does match.

### 2.3 The rest of the filter contract does not match either

Same root cause, wider blast radius. `FederationQuery` sends parameter names the
endpoint does not declare:

| `FederationQuery` sends | Endpoint declares | Effect |
|---|---|---|
| `organism` | `organism_name` | dropped |
| `date_collected_from` | `date_from` | dropped |
| `date_collected_to` | `date_to` | dropped |
| `quality_tier_min` | `quality_status` (different semantics) | dropped |
| `page_size` | `per_page` | dropped |
| `country` | *(no such parameter)* | dropped |
| `state` | *(no such parameter)* | dropped |
| `source_type` | `source_type` | applied |
| `page` | `page` | applied |

A federated query is therefore effectively **unfiltered**: it asks for one narrow
slice and requests the partner's whole sample list, one page at a time.

This has a safety consequence beyond correctness. `client.py:161-162` forces
`quality_tier_min=ANALYZABLE` onto every outbound request, and
`models.py:104-108` documents that floor as the reason no PRELIMINARY samples
cross a federation boundary. The partner discards the parameter, so **that floor
is not enforced on the wire**. Whatever tier filtering happens is whatever the
partner applies on its own.

### 2.4 There is no peer-facing query endpoint to paginate against

The client targets the partner's `GET /api/v1/samples/`. That endpoint resolves
its caller through `get_current_user` (`backend/backend/auth/guards.py:17`),
which branches on `ENV` and then on the `access` cookie — it has no
federation-key path. Only `/federation/push` and `/federation/access-requests`
call `authenticate_federation_peer` (`routers/federation.py:291,351`).

So a partner receiving the fan-out returns **401 in production**. Under
`ENV=local` the request falls through to the mock Platform Admin
(`guards.py:24-36`), which would give a peer admin-level visibility.

---

## 3. The pagination work

Ordered so each step is verifiable on its own. Steps 1 and 2 are blocked on the
design decisions in section 4.

1. **Align the outbound parameter names** with the receiving endpoint, including
   `page_size` to `per_page`. Decide per row in the 2.3 table whether the client
   name or the endpoint name is the one that changes — `country` and `state` have
   no endpoint counterpart and need one added or the fields dropped.
2. **Send the page size.** Wire `DEFAULT_PER_PARTNER_PAGE_SIZE` into the request
   params, or delete the constant if `FederationQuery.page_size` is meant to be
   the only source.
3. **Follow pages** until `pagination.pages` is exhausted, **with a hard cap**.
   An uncapped follow-loop against a hostile or broken peer is an unbounded
   memory commitment, and `_query_one` has no response-size limit today either.
   Cap both the page count and the total rows accepted per partner.
4. **Decide the partial-result contract.** If a partner's page 3 fails after
   pages 1 and 2 succeeded, does that partner contribute its partial rows or
   none? Today a partner failure drops the whole partner
   (`client.py:128-139`, `return_exceptions=True`); multi-page fetching makes
   partial success newly possible and the choice must be explicit.
5. **Surface truncation.** When the cap is hit, the caller needs to know the
   result set is incomplete. A merged result list that silently omits rows is
   the same class of failure as the envelope-key bug — it reads as "no more
   matches" rather than "we stopped looking."

---

## 4. Design questions to settle first

- **Should `quality_tier_min` be a client-supplied parameter at all?** A floor
  that the requester sends is a floor the requester can lower. It belongs
  server-side, enforced by the peer against the requesting instance's role.
- **What does a peer-facing query endpoint look like?** It needs
  `require_federation_peer`, a server-enforced sharing-level floor, and a
  pagination contract this client can rely on. Building it is the natural place
  to fix 2.3 and 2.4 together.
- **Cap values.** Pages per partner, rows per partner, and bytes per response.

---

## 5. How to verify this work

**Do not trust a green suite in this area.** Three of the defects above were
invisible precisely because the tests encoded the same wrong assumption as the
code: every partner mock in `tests/federation/test_client.py` and
`tests/test_federation_router_api.py` hand-wrote a `results` key that no JACKPOT
endpoint emits, so the suite passed against a contract that did not exist.
`test_search_fans_out_to_enabled_partners` still passes today while verifying a
fan-out that cannot work against a real peer.

`545be64` replaced those hand-written payloads with `_envelope` / `_partner_envelope`
helpers that build the mock body by calling `success_list` — the same helper the
samples router uses. **Keep that property.** Any new pagination test must derive
its mock envelope from the real helper, so the `pagination` block it asserts
against is the one the server actually emits.

A useful check when the work lands: reintroduce the defect and confirm the suite
fails. Before `545be64` the envelope-key bug passed every test in the file; after
it, reintroducing the same bug fails eight.

---

## 6. References

- `backend/backend/federation/client.py` — `FederationClient`, `_query_one`
- `backend/backend/federation/models.py` — `FederationQuery`, `FederationQueryResult`
- `backend/backend/routers/samples.py` — the `GET /` list endpoint being queried
- `backend/backend/responses.py` — `success_list`, the envelope contract
- `backend/backend/auth/guards.py` — `get_current_user`, `authenticate_federation_peer`
- `docs/federation.md` — federation architecture, three levels
- `docs/federation_operations.md` — operator-facing federation reference
