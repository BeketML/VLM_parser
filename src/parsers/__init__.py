"""Парсеры для обработки PDF."""
from .pymupdf_parser import PyMuPDFParser
from .vlm_parser import VLMParser

__all__ = ["PyMuPDFParser", "VLMParser"]