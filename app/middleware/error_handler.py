from fastapi import status

class DomainException(Exception):
    """Base exception for all internal domain-level errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(DomainException):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


class ValidationError(DomainException):
    def __init__(self, message: str = "Invalid input."):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST)


class FileProcessingError(DomainException):
    def __init__(self, message: str = "Error processing file."):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
