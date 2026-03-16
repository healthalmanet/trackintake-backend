from cloudinary_storage.storage import MediaCloudinaryStorage
import os

from cloudinary_storage.storage import MediaCloudinaryStorage
import os

class CustomCloudinaryStorage(MediaCloudinaryStorage):
    """
    Custom storage to handle both image and raw file uploads correctly,
    and make them publicly accessible.
    """

    def _get_resource_type(self, name):
        ext = os.path.splitext(name)[1].lower()
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return 'image' if ext in image_extensions else 'raw'

    def _get_upload_options(self, name):
        options = super()._get_upload_options(name)
        options['resource_type'] = self._get_resource_type(name)
        options['access_mode'] = 'public'  # 👈 crucial to avoid 401
        return options

    def _get_url_options(self, name):
        options = super()._get_url_options(name)
        options['resource_type'] = self._get_resource_type(name)
        return options

# testing