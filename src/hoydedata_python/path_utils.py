from pathlib import Path


def validate_and_convert_path(path_input: str | Path) -> Path:
    """
    Validate and convert path input to Path object.

    Args:
        path_input: Path as string or Path object

    Returns:
        Validated Path object

    Raises:
        ValueError: If path is invalid or empty
        TypeError: If path is not string or Path object
    """
    if not path_input:
        raise ValueError("Path cannot be empty or None")

    if isinstance(path_input, str):
        if not path_input.strip():
            raise ValueError("Path string cannot be empty or whitespace only")
        path_obj = Path(path_input)
    elif isinstance(path_input, Path):
        path_obj = path_input
    else:
        raise TypeError(f"Path must be string or Path, got {type(path_input)}")

    # Validate that the path is not just dots or invalid characters
    try:
        path_obj.resolve()  # This will raise an exception for invalid paths
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid path '{path_input}': {e}")

    return path_obj


def ensure_output_directory(output_path: Path) -> Path:
    """
    Ensure output directory exists and return the directory path.

    Args:
        output_path: Path to output file or directory

    Returns:
        Directory path where files will be saved
    """
    if output_path.suffix:
        # It's a file path, get the parent directory
        output_dir = output_path.parent
    else:
        # It's already a directory path
        output_dir = output_path

    # Create directory if it doesn't exist
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise PermissionError(f"No permission to create directory: {output_dir}")
    except OSError as e:
        raise OSError(f"Failed to create directory {output_dir}: {e}")

    return output_dir
