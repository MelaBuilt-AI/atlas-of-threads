import json


print(
    json.dumps(
        {
            "prose": "Without that premise, the medium remains useful as a workspace.",
            "nodes": [
                {
                    "local_id": "new_claim",
                    "kind": "claim",
                    "text": "The medium remains useful as a workspace.",
                    "status": "accepted",
                }
            ],
            "edges": [],
        }
    )
)
