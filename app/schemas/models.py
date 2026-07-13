import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ExcelUploadResponse(BaseModel):
    columns: list[str]
    preview_rows: list[dict[str, str]]
    excel_id: str = ""


class PdfUploadResponse(BaseModel):
    pdf_id: str
    page_count: int
    filename: str


class TemplateField(BaseModel):
    column: str
    page: int = Field(default=1, ge=1)
    x: float
    y: float
    font_size: float = Field(default=11, ge=6, le=36)
    max_width: float | None = None
    type: Literal["column", "text"] = "column"
    text_value: str = ""

    @field_validator("x", "y")
    @classmethod
    def _reject_nan_inf(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Coordinate must be a finite number")
        return v

    @field_validator("column")
    @classmethod
    def _strip_column(cls, v: str) -> str:
        return v.strip()


class TemplateSaveRequest(BaseModel):
    name: str = Field(min_length=1)
    pdf_file: str
    fields: list[TemplateField]


class TemplateSaveResponse(BaseModel):
    id: str
    name: str
    pdf_file: str
    version: int
    field_count: int
    page_count: int = 1
    created_at: str
    warnings: list[str] = []


class TemplateListItem(BaseModel):
    id: str
    name: str
    pdf_file: str
    version: int
    created_at: str
    field_count: int
    page_count: int = 1


class TemplateRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TemplateDuplicateRequest(BaseModel):
    name: str | None = None


class AdjustFieldRequest(BaseModel):
    column: str
    page: int = Field(ge=1)
    font_size: float | None = Field(default=None, ge=6, le=36)
    x: float | None = None
    y: float | None = None

    @field_validator("x", "y")
    @classmethod
    def _reject_nan_inf(cls, v: float | None) -> float | None:
        if v is not None and (math.isnan(v) or math.isinf(v)):
            raise ValueError("Coordinate must be a finite number")
        return v


class FillStartResponse(BaseModel):
    batch_id: str
    warnings: list[str] = []


class FillStatusResponse(BaseModel):
    batch_id: str
    status: str
    completed: int
    total: int
    error: str | None = None
    warnings: list[str] = []
    files: list[str] = []

