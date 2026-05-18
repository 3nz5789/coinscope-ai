-- COI-101 — model registry for trained ML artifacts (HMM regime, classifier, etc.).
-- One row per (model_type, symbol, version). `active` flips to TRUE only when a
-- model passes its validation gate; the engine reads where active = TRUE.

CREATE TABLE IF NOT EXISTS model_registry (
    id            SERIAL        PRIMARY KEY,
    model_type    TEXT          NOT NULL,
    symbol        TEXT          NOT NULL,
    version       TEXT          NOT NULL,
    path          TEXT          NOT NULL,
    trained_at    TIMESTAMPTZ   NOT NULL,
    val_accuracy  NUMERIC(5,4)  NOT NULL,
    feature_set   TEXT[]        NOT NULL,
    active        BOOLEAN       NOT NULL DEFAULT FALSE,
    UNIQUE (model_type, symbol, version)
);

CREATE INDEX IF NOT EXISTS model_registry_active_idx
    ON model_registry (model_type, symbol)
    WHERE active = TRUE;
