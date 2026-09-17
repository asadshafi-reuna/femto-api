# femto — database schema

MongoDB. Metadata only: model files and generated C live in blob storage.

## users
```jsonc
{
  "_id": ObjectId,
  "email": "ayaan@nucleus.dev",        // unique index
  "password_hash": "$2b$...",          // bcrypt, never returned by the API
  "plan": "free",                      // free | pro | enterprise
  "credits": 0,                        // prepaid artifact unlocks

  "profile": {                         // <- the 7-question onboarding
    "name": "Ayaan Khan",
    "company": "Nucleus Wearables",
    "role": "Embedded / Firmware Engineer",
    "role_other": null,
    "phone": { "country_code": "+44", "number": "7911084712" },
    "region": "United Kingdom",
    "targets": ["ARM Cortex-M", "Nordic nRF"],
    "purpose": "Prototype / Evaluation",
    "purpose_detail": "keyword spotting on nRF5340"
  },

  "onboarding": { "completed": true, "completed_at": ISODate, "version": 1 },

  "github": {
    "linked": true,
    "login": "ayaan",
    "avatar_url": "https://...",
    "scope": "repo",                   // public_repo | repo (private included)
    "token_enc": "gAAAA...",           // Fernet-encrypted, NEVER returned
    "linked_at": ISODate
  },

  "meta": { "locale": "en-GB", "referrer": "...", "utm": {} },
  "created_at": ISODate
}
```

## conversions
```jsonc
{
  "_id": ObjectId,
  "user_id": ObjectId,                 // owner; every query filters on this
  "name": "mnist_cnn.onnx",
  "target": "cortex-m4f",
  "quant": "int8",
  "goal": "size",

  "source": {
    "kind": "github",                  // upload | github | sample
    "filename": "mnist_cnn.onnx",
    "blob_key": "models/<user>/<conv>/model.onnx",
    "repo": "Reuna-AI/models",         // github-sourced only
    "ref": "main",
    "path": "models/mnist_cnn.onnx"
  },

  "status": "done",                    // queued | building | done | failed
  "flash": "24.1 KB",
  "ram": "3.2 KB",
  "error": null,

  "artifact": {
    "ready": true,
    "files": ["model.c", "model.h"],
    "size_bytes": 24680,
    "sha256": "4f884ab...",
    "line_count": 812,
    "preview_text": "/* model.c ... */"  // first lines, shown to locked users
  },

  "unlocked": false,                   // paid / entitled?
  "unlock_source": "purchase",         // purchase | credit | plan
  "created_at": ISODate
}
```

## orders
```jsonc
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "kind": "single_unlock",             // single_unlock | credit_pack | plan_upgrade
  "conversion_id": ObjectId,           // single_unlock only
  "quantity": 1,
  "amount_cents": 900,
  "currency": "usd",
  "status": "paid",                    // pending | paid | failed | refunded
  "provider": "stripe",
  "provider_ref": "cs_test_...",
  "created_at": ISODate,
  "paid_at": ISODate
}
```

## oauth_states
Short-lived CSRF protection for the GitHub flow. TTL index removes rows after
10 minutes automatically.
```jsonc
{ "state": "random", "user_id": ObjectId, "scope": "repo", "created_at": ISODate }
```

## Indexes
| collection | index | why |
|---|---|---|
| users | `email` unique | login lookup, prevents duplicates |
| users | `github.login` | find by linked account |
| conversions | `user_id, created_at desc` | the dashboard list |
| conversions | `user_id, status` | status filters |
| orders | `user_id, created_at desc` | billing history |
| orders | `provider_ref` | webhook lookup |
| oauth_states | `created_at` TTL 600s | self-cleaning |
| oauth_states | `state` unique | one-time use |

## Rules that must not drift
- `password_hash` and `github.token_enc` are never serialized to the client.
  `serializers.py` is the single place that builds public shapes.
- Every conversion query filters by `user_id` — a user can never read another's.
- `unlocked` is only ever set by the billing webhook or a credit spend, never
  by anything the browser sends.
