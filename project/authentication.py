# from asgiref.sync import async_to_sync
# from channels.db import database_sync_to_async
# from rest_framework_simplejwt.authentication import JWTAuthentication

# class FinalJWTAuthentication(JWTAuthentication):
#     """
#     This is the definitive, unified JWT authenticator for ASGI applications.
#     It works for BOTH synchronous and asynchronous views without errors.
    
#     Its public `authenticate` method is synchronous, as required by DRF.
#     Inside, it uses a robust async bridge to run the blocking database
#     call in a separate thread, which is safe in all contexts.
#     """
#     def authenticate(self, request):
#         """
#         This method remains synchronous to be compatible with DRF's core.
#         """
#         # First, perform the standard, non-database token validation.
#         # This will raise an InvalidToken exception if the token is bad,
#         # which is correctly handled by DRF.
#         header = self.get_header(request)
#         if header is None:
#             return None

#         raw_token = self.get_raw_token(header)
#         if raw_token is None:
#             return None
        
#         validated_token = self.get_validated_token(raw_token)

#         # Now, perform the database lookup using our robust async bridge.
#         # This is the crucial part that solves all previous errors.
#         user = self.get_user_safely(validated_token)
        
#         if user is None:
#             return None

#         return user, validated_token

#     def get_user_safely(self, validated_token):
#         """
#         This function is the core of the solution.
#         1. It wraps the original, blocking `get_user` method to be async-safe.
#         2. It calls that wrapped function from a sync context using `async_to_sync`.
#         This pattern correctly delegates the DB call to a thread, avoiding all errors.
#         """
#         # Create an awaitable, thread-safe version of the blocking DB call
#         get_user_async_safe = database_sync_to_async(super().get_user)
        
#         # Call the awaitable function from our current sync context
#         try:
#             return async_to_sync(get_user_async_safe)(validated_token)
#         except Exception:
#             return None


from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class FinalJWTAuthentication(JWTAuthentication):
    """
    Unified JWT authenticator for Django + DRF.
    Runs direct synchronous DB lookup without nesting async_to_sync / database_sync_to_async,
    completely preventing ASGI worker thread cancellation deadlocks when clients abort/disconnect.
    """

    def authenticate(self, request):
        # 1. Extract header
        header = self.get_header(request)
        if header is None:
            return None  # No auth attempted (OK)

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None  # No token provided (OK)

        # 2. Validate token (signature, expiry, etc.)
        validated_token = self.get_validated_token(raw_token)

        # 3. Fetch user safely (DB access)
        user = self.get_user_safely(validated_token)

        if user is None:
            # THIS MUST BE AN ERROR, NOT NONE
            raise AuthenticationFailed("User not found")

        return user, validated_token

    def get_user_safely(self, validated_token):
        """
        Directly fetches user for validated token.
        Avoids wrapping with async_to_sync, eliminating threadpool deadlocks on ASGI disconnects.
        """
        try:
            return super().get_user(validated_token)
        except AuthenticationFailed:
            # Token valid but user invalid → MUST propagate
            raise
        except Exception as exc:
            # Any unexpected error should fail authentication
            raise AuthenticationFailed("Authentication error") from exc
