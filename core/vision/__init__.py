"""Vision utilities shared across puzzle parsers."""

from .line_projection import LineGroup, extract_line_groups, select_regular_line_subset
from .ocr import CosineTemplateMatcher, DistanceWeightedKnn, OcrCandidate, OcrPrediction
from .parsed_board_payload import build_parsed_board_payload

__all__ = [
    "CosineTemplateMatcher",
    "DistanceWeightedKnn",
    "LineGroup",
    "OcrCandidate",
    "OcrPrediction",
    "build_parsed_board_payload",
    "extract_line_groups",
    "select_regular_line_subset",
]
