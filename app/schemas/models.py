from pydantic import BaseModel, Field


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
    page: int = 0
    x: float
    y: float
    font_size: float = Field(default=11, ge=6, le=36)
    max_width: float | None = None


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
    created_at: str
    warnings: list[str] = []


class TemplateListItem(BaseModel):
    id: str
    name: str
    pdf_file: str
    version: int
    created_at: str
    field_count: int


class TemplateRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TemplateDuplicateRequest(BaseModel):
    name: str | None = None


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


class RouteEntry(BaseModel):
    value: str = Field(min_length=1)
    template_id: str = Field(min_length=1)


class WorkflowSaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    routing_column: str = Field(min_length=1)
    routes: list[RouteEntry] = Field(min_length=1)


class WorkflowSaveResponse(BaseModel):
    id: str
    name: str
    routing_column: str
    route_count: int
    created_at: str


class WorkflowListItem(BaseModel):
    id: str
    name: str
    routing_column: str
    route_count: int
    created_at: str
