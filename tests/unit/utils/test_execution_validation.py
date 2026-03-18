import pytest

from agent_pump.utils.execution import SecureExecutor


def test_validate_image_name_valid():
    """Test valid image names."""
    valid_images = [
        "python:3.11-slim",
        "node:18",
        "ubuntu",
        "my-registry.com/user/image:tag",
        "user/image",
        "image@sha256:1234567890abcdef",
        "my_image.v1",
    ]
    for image in valid_images:
        SecureExecutor._validate_image_name(image)


def test_validate_image_name_invalid_start_dash():
    """Test image names starting with dash."""
    with pytest.raises(ValueError, match="cannot start with '-'"):
        SecureExecutor._validate_image_name("-privileged")
    with pytest.raises(ValueError, match="cannot start with '-'"):
        SecureExecutor._validate_image_name("--network=host")


def test_validate_image_name_invalid_whitespace():
    """Test image names with whitespace."""
    with pytest.raises(ValueError, match="cannot contain whitespace"):
        SecureExecutor._validate_image_name("ubuntu --privileged")
    with pytest.raises(ValueError, match="cannot contain whitespace"):
        SecureExecutor._validate_image_name("image tag")


def test_validate_image_name_invalid_chars():
    """Test image names with invalid characters."""
    invalid_chars = [";", "&", "|", ">", "<", "$", "`", "\\", "!", '"', "'"]
    for char in invalid_chars:
        with pytest.raises(ValueError, match="contains invalid characters"):
            SecureExecutor._validate_image_name(f"image{char}test")


def test_validate_image_name_empty():
    """Test empty image name."""
    with pytest.raises(ValueError, match="cannot be empty"):
        SecureExecutor._validate_image_name("")
