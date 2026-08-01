"""Component models for the Virtual Bench.

Phase 0 defined what a model must prove (`_schema.py`); the models now
exist: U1 ESP32-S3, U2 IP5306, U3 SY8089, U5 PAM8403, Q1 SI2301, DS1
ILI9488, the microSD card and BT1 the battery — every parameter cited to
a page of a PDF in `hardware/datasheets/`, or explicitly derived. A model
added here before its datasheet is in `hardware/datasheets/` fails
`require_valid()`, which is the point. (This docstring once said the
directory was empty on purpose — a claim that outlived its truth by a
full phase.)
"""

from ._schema import (  # noqa: F401
    DatasheetRef,
    Model,
    ModelSchemaError,
    Param,
    Pin,
    require_valid,
    validate_locator,
    validate_model,
)
