print(
    "A changed context still produces an inspectable medium.\n\n"
    "```thought-graph\n"
    '{"nodes": ['
    '{"local_id": "claim", "kind": "claim", '
    '"text": "A changed context still produces an inspectable medium.", '
    '"status": "accepted"},'
    '{"local_id": "judgment", "kind": "judgment_call", '
    '"text": "Keep the medium human-readable.", "status": "accepted"},'
    '{"local_id": "rejected1", "kind": "rejected_alternative", '
    '"text": "Treat the graph as neural ground truth.", "status": "rejected"},'
    '{"local_id": "rejected2", "kind": "rejected_alternative", '
    '"text": "Discard the context lineage.", "status": "rejected"}'
    '], "edges": ['
    '{"from": "judgment", "to": "claim", "kind": "shapes"},'
    '{"from": "rejected1", "to": "claim", "kind": "rejects"},'
    '{"from": "rejected2", "to": "claim", "kind": "rejects"}'
    "]}\n"
    "```"
)
