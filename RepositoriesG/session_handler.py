from functools import wraps

def session_handler(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)  # Execute the original function
            return result
        finally:
            # Ensure the session is closed after the function is done
            if hasattr(self, 'db_session'):
                self.db_session.close()
    return wrapper
