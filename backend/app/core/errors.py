class AppError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = 'request_error'):
        self.message, self.status, self.code = message, status, code
