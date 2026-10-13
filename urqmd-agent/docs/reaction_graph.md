# Temporal bipartite reaction graph — design rationale

## Why UID alone is insufficient as a graph node

UrQMD's `uid` is a *particle identity*: a unique lifetime tag assigned at
creation (`init.f:543`, `scatter.f:1042`) and carried until the particle is
consumed. It is **not** a unique label for a point on the particle's
worldline. The real Phase-0 event contains interactions in which the same uid
is both incoming and outgoing (e.g. UID 44 passes identically through ctags
18, 40, 47, 59 — elastic, identity-preserving scattering).

If graph nodes were keyed by uid, such an interaction would produce

    uid 44  ->  interaction 18  ->  uid 44

i.e. an artificial directed self-cycle. Cycles break topological ordering,
time traversal, and ancestry queries — yet nothing acausal happened: the
*state before* and the *state after* the scattering are physically distinct
(different momentum, position, collision count).

## Particle identity vs particle state

The graph therefore distinguishes three kinds of objects:

1. **Particle identity** — the UrQMD `uid` (an attribute, not a node key).
2. **Particle state / snapshot** — the full state vector (position,
   four-momentum, type, charge, collision counters) of one uid immediately
   before or after one specific interaction. Node key:
   `StateId(ctag, role, ordinal)`. One uid maps to many state nodes.
3. **Interaction** — one UrQMD collision/decay record, keyed by `ctag`.

Edges run only forward through one record:

    incoming states  ->  interaction  ->  outgoing states

so the graph is bipartite (state nodes ↔ interaction nodes) and temporal.

## Worldline continuity

If the same uid appears as an outgoing state of an earlier interaction and as
an incoming state of a later one, a **worldline link**
(`WorldlineLink(uid, from_state, to_state)`, always with
`from_ctag < to_ctag`) records "this is the same particle continuing".
Worldline links connect *distinct state nodes*; they never merge nodes.

## Identity-preserving scattering

If the same uid is incoming and outgoing in the SAME interaction, an
**identity passage** (`IdentityPassage`) is recorded explicitly between two
distinct state nodes of that interaction. This is the correct representation
of elastic/identity-preserving transport: the particle keeps its identity but
changes state. It is never collapsed into a self-loop.

## Generic many-body reactions are hyperedges

For a generic 2->n reaction, UrQMD writes the incoming set and the outgoing
set — nothing more. Any one-to-one assignment "incoming particle A became
outgoing particle B" would be an arbitrary, scientifically invalid invention:
the file15 record contains no such information, and quantum-mechanically the
final state of a 2->n scattering is not a labelled pairing of in- and
out-lines. The graph therefore exposes only the sets:

    {incoming states} -> interaction -> {outgoing states}

`reaction_reactants(ctag)` / `reaction_products(ctag)` return the sets;
`producers(uid)` / `consumers(uid)` return interaction lists. Ancestry
queries (`ancestors_of_state`, `trace_back`) traverse whole incoming sets —
never a guessed single parent.

## Decay-specific mother/daughter semantics

The single exception is the 1->n decay, verified in Phase 0 as
`process_id == 20` with `nin == 1` (scatter.f:173 sets iline=20 for decays;
file15out writes nin=1 when ind2=0, output.f:501-503). Here the unique
incoming particle is unambiguously the mother of all outgoing daughters, so
`decay_mother(state)` / `decay_daughters(state)` are exposed — but **only**
for records passing this classification. These methods return `None`/`()` for
any non-decay interaction.

## Termination guarantee

Because (a) interaction nodes are keyed by the strictly increasing ctag,
(b) worldline links only go from earlier to later ctags, and (c) identity
passages connect the incoming state to the outgoing state *within* one
interaction (in→out direction, matching time order), all ancestry/descendant
walks are finite. The walks additionally carry visited-sets, so even
pathological input cannot loop.
