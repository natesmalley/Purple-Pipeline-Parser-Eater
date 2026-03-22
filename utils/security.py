"""Security utilities for path validation and sanitization."""

from __future__ import annotations

from pathlib import Path
import os


class SecurityError(Exception):
    """Security violation detected."""
    pass


def validate_path(user_path: str, base_dir: Path, allow_absolute: bool = False) -> Path:
    """
    Validate and resolve path, preventing path traversal attacks.
    
    Args:
        user_path: User-provided path (can be relative or absolute)
        base_dir: Base directory that the path must be within
        allow_absolute: If True, allows absolute paths (still validated to be within base_dir)
    
    Returns:
        Resolved Path object that is guaranteed to be within base_dir
    
    Raises:
        SecurityError: If path traversal is detected
        FileNotFoundError: If path doesn't exist
        ValueError: If path is not a file/directory as expected
    """
    base_dir = base_dir.resolve()
    
    if os.path.isabs(user_path):
        if not allow_absolute:
            raise SecurityError(
                f"Absolute paths not allowed: '{user_path}'. "
                f"Please provide a relative path from '{base_dir}'"
            )
        # Resolve absolute path and check if it's within base_dir
        resolved = Path(user_path).resolve()
        if not str(resolved).startswith(str(base_dir)):
            raise SecurityError(
                f"Path traversal detected: Path '{user_path}' "
                f"resolves to '{resolved}' which is outside allowed directory '{base_dir}'"
            )
        return resolved
    else:
        # Resolve relative path
        resolved = (base_dir / user_path).resolve()
        
        # Ensure resolved path is within base directory
        if not str(resolved).startswith(str(base_dir)):
            raise SecurityError(
                f"Path traversal detected: Path '{user_path}' "
                f"resolves to '{resolved}' which is outside allowed directory '{base_dir}'"
            )
        
        return resolved


def validate_file_path(user_path: str, base_dir: Path, allow_absolute: bool = False) -> Path:
    """
    Validate file path, preventing path traversal attacks.
    
    Args:
        user_path: User-provided file path
        base_dir: Base directory that the file must be within
        allow_absolute: If True, allows absolute paths
    
    Returns:
        Resolved Path object that is guaranteed to be within base_dir and is a file
    
    Raises:
        SecurityError: If path traversal is detected
        FileNotFoundError: If file doesn't exist
        ValueError: If path is not a file
    """
    resolved = validate_path(user_path, base_dir, allow_absolute)
    
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")
    
    if not resolved.is_file():
        raise ValueError(f"Path is not a file: {resolved}")
    
    return resolved


def validate_dir_path(user_path: str, base_dir: Path, allow_absolute: bool = False) -> Path:
    """
    Validate directory path, preventing path traversal attacks.
    
    Args:
        user_path: User-provided directory path
        base_dir: Base directory that the directory must be within
        allow_absolute: If True, allows absolute paths
    
    Returns:
        Resolved Path object that is guaranteed to be within base_dir and is a directory
    
    Raises:
        SecurityError: If path traversal is detected
        FileNotFoundError: If directory doesn't exist
        ValueError: If path is not a directory
    """
    resolved = validate_path(user_path, base_dir, allow_absolute)
    
    if not resolved.exists():
        raise FileNotFoundError(f"Directory not found: {resolved}")
    
    if not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {resolved}")
    
    return resolved


def safe_create_dir(user_path: str, base_dir: Path, allow_absolute: bool = False) -> Path:
    """
    Safely create directory path, preventing path traversal attacks.
    
    Args:
        user_path: User-provided directory path to create
        base_dir: Base directory that the directory must be within
        allow_absolute: If True, allows absolute paths
    
    Returns:
        Resolved Path object that is guaranteed to be within base_dir
    
    Raises:
        SecurityError: If path traversal is detected
    """
    base_dir = base_dir.resolve()
    
    if os.path.isabs(user_path):
        if not allow_absolute:
            raise SecurityError(
                f"Absolute paths not allowed: '{user_path}'. "
                f"Please provide a relative path from '{base_dir}'"
            )
        resolved = Path(user_path).resolve()
        if not str(resolved).startswith(str(base_dir)):
            raise SecurityError(
                f"Path traversal detected: Path '{user_path}' "
                f"would create directory outside allowed directory '{base_dir}'"
            )
    else:
        resolved = (base_dir / user_path).resolve()
        if not str(resolved).startswith(str(base_dir)):
            raise SecurityError(
                f"Path traversal detected: Path '{user_path}' "
                f"would create directory outside allowed directory '{base_dir}'"
            )
    
    # Create directory if it doesn't exist
    resolved.mkdir(parents=True, exist_ok=True)
    
    return resolved

