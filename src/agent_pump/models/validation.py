from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
import string

class ProjectPathInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v:
            raise ValueError("Path cannot be empty")
        
        try:
            path_obj = Path(v).expanduser().resolve()
        except Exception:
             raise ValueError(f"Invalid path format: {v}")
        
        if not path_obj.exists():
            raise ValueError(f"Path does not exist: {v}")
        
        if not path_obj.is_dir():
            raise ValueError(f"Path is not a directory: {v}")
            
        return str(path_obj)

class IdeaInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    
    idea: str = Field(..., min_length=5, max_length=500)

class PromptCustomizationInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    
    template: str

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if not v.strip():
             raise ValueError("Template cannot be empty")
        
        # Check for matching braces to ensure valid format string
        try:
            # string.Formatter().parse(v) yields tuples (literal_text, field_name, format_spec, conversion)
            list(string.Formatter().parse(v))
        except ValueError as e:
            raise ValueError(f"Invalid template format: {e}")
            
        return v
