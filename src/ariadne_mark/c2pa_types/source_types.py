# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Adapted for Ariadne Mark on 2026-11-06: module documentation only.
# Upstream: trufo-ai/trufo-py, commit 24dd6478e2b5ce753e34abb2c557707c12dd8d40
"""IPTC/C2PA vocabulary reused under Apache-2.0; not a compliance policy."""

from enum import Enum

_IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"


class DigitalSourceType(str, Enum):
    """IPTC and C2PA source types, including legacy values for reading manifests."""

    DIGITAL_CAPTURE = f"{_IPTC}digitalCapture"
    COMPUTATIONAL_CAPTURE = f"{_IPTC}computationalCapture"
    COMPOSITE_CAPTURE = f"{_IPTC}compositeCapture"
    SCREEN_CAPTURE = f"{_IPTC}screenCapture"
    NEGATIVE_FILM = f"{_IPTC}negativeFilm"
    POSITIVE_FILM = f"{_IPTC}positiveFilm"
    PRINT = f"{_IPTC}print"
    DIGITAL_CREATION = f"{_IPTC}digitalCreation"
    ALGORITHMIC_MEDIA = f"{_IPTC}algorithmicMedia"
    DATA_DRIVEN_MEDIA = f"{_IPTC}dataDrivenMedia"
    HUMAN_EDITS = f"{_IPTC}humanEdits"
    ALGORITHMICALLY_ENHANCED = f"{_IPTC}algorithmicallyEnhanced"
    COMPOSITE = f"{_IPTC}composite"
    COMPOSITE_SYNTHETIC = f"{_IPTC}compositeSynthetic"
    TRAINED_ALGORITHMIC_MEDIA = f"{_IPTC}trainedAlgorithmicMedia"
    VIRTUAL_RECORDING = f"{_IPTC}virtualRecording"
    COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA = f"{_IPTC}compositeWithTrainedAlgorithmicMedia"

    # Legacy IPTC value retained for reading, not new declarations.
    DIGITAL_ART = f"{_IPTC}digitalArt"

    # C2PA extensions; availability is controlled by each operation.
    EMPTY = "http://c2pa.org/digitalsourcetype/empty"
    TRAINED_ALGORITHMIC_DATA = "http://c2pa.org/digitalsourcetype/trainedAlgorithmicData"
